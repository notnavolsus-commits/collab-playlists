import functools
import json
import asyncio
import logging

from django.conf import settings
from django.apps import apps
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import PermissionDenied, ValidationError
from time import time

from tornado.websocket import WebSocketClosedError
from twisted.internet.error import ConnectionClosed

from .stores import BroadcastRedisStore
from .services import ChatService, BroadcastService
from .db import *

logger = logging.getLogger(__name__)


def creator_only(handler):
    @functools.wraps(handler)
    async def wrapper(self, data):
        if not self.is_creator:
            await self.close()
            raise PermissionDenied('This action is permitted only for creators!')
        return await handler(self, data)

    return wrapper


class ConsumerInRoom(AsyncWebsocketConsumer):
    ACTION_HANDLERS = {
        'vote': '_handle_vote',
        'start_broadcast': '_handle_start_broadcast',
        'pause_broadcast': '_handle_pause_broadcast',
        'resume_broadcast': '_handle_resume_broadcast',
        'stop_broadcast': '_handle_stop_broadcast',
        'chat_message': '_handle_chat_message',
    }

    async def connect(self) -> None:
        Room = apps.get_model('rooms', 'Room')
        self.room_slug = self.scope['url_route']['kwargs']['room_slug']
        self.room_group_name = f'room_{self.room_slug}'
        self.is_creator = False
        self.heartbeat_task = None
        self.current_track_id: int | None = None
        try:
            room = await get_room_by_slug(room_slug=self.room_slug)
            self.room_id = room.id
        except Room.DoesNotExist:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        self.is_creator = await room_creator_validation(room, self.scope['user'])
        await self.accept()

        if self.is_creator:
            self.start_heartbeat()
        self.chat_service = ChatService(self.room_group_name, self.channel_layer)
        self.broadcast_service = BroadcastService(self.room_group_name, self.channel_layer)
        history = await ChatService.get_history_chat(room_id=room.id)
        for msg in history:
            await self.send(text_data=json.dumps({
                'action': 'chat_message',
                'username': msg['username'],
                'message': msg['message'],
                'timestamp': msg['timestamp'],
                'avatar_url': str(msg['avatar_url']),
            }))
        try:
            state = await BroadcastRedisStore.get_state(room.id)
            if state and state.get('track_id') != 'none':
                await self.send(text_data=json.dumps({
                    'action': 'sync_state',
                    'track_id': int(state['track_id']),
                    'current_time': float(state['current_time']),
                    'is_playing': state.get('is_playing') == 'true',
                    'started_by': state.get('started_by', ''),
                    'last_update': int(state.get('last_update', 0)),
                }))
            self.current_track_id = None if state['track_id'] == 'none' else state['track_id']

        except Exception as e:
            logger.error(f'Error in saving data to Redis while writing in db broadcast state: {e}')
        logger.debug('Websocket connected!')

    async def disconnect(self, close_code) -> None:
        logger.debug(msg='Websocket disconnecting')
        await self.stop_heartbeat()
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None) -> None:
        if text_data:
            try:
                data = json.loads(text_data)
                action = data['action']
                handler = ConsumerInRoom.ACTION_HANDLERS.get(action)
                if handler:
                    await getattr(self, handler)(data)
                else:
                    raise ValueError('No such action: ', action)
            except Exception as e:
                logger.error(f'Error in serialization a message from websocket: {e}')

    def start_heartbeat(self) -> None:
        logger.debug('start heartbeating')
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        self.heartbeat_task = None

    async def _handle_vote(self, data: dict) -> None:
        if not self.scope['user'].is_authenticated: return
        room_track_id = data['room_track_id']
        if not await validate_room_track_in_room(self.room_id, room_track_id):
            raise ValidationError("room_track must belong to the same room")
        toggle_dict = await toggle_vote(self.scope['user'].id, room_track_id)
        if toggle_dict:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_vote_update',
                    **toggle_dict
                }
            )

    async def _handle_chat_message(self, data: dict):
        user = self.scope['user']
        await self.chat_service.chat_message(data, user, self.room_slug)

    @creator_only
    async def _handle_start_broadcast(self, data: dict) -> None:
        room_track_id = data['track_id']
        if not await validate_room_track_in_room(self.room_id, room_track_id):
            raise ValidationError('room_track can\'t be in other room')
        user = self.scope['user']
        try:
            await move_room_track_to_playing_zone(room_track_id, self.room_id)
            await BroadcastRedisStore.save_broadcast_state(self.room_id, {'track_id': str(room_track_id),
                                                                          'current_time': '0',
                                                                          'is_playing': 'true',
                                                                          'started_by': user.username,
                                                                          'room_slug': self.room_slug})
            self.current_track_id = room_track_id
        except Exception as e:
            logger.error(f'Error while saving data to Redis while starting broadcast: {e}')
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'start_broadcast',
                'action': 'start_broadcast',
                'track_id': room_track_id,
            }
        )
        logger.debug(f'start broadcast with track id {room_track_id}')

    @creator_only
    async def _handle_pause_broadcast(self, data) -> None:
        username = self.scope['user'].username
        await self.broadcast_service.set_playing('pause', self.room_id, username)

    @creator_only
    async def _handle_resume_broadcast(self, data) -> None:
        username = self.scope['user'].username
        await self.broadcast_service.set_playing('resume', self.room_id, username)

    @creator_only
    async def _handle_stop_broadcast(self, data: dict) -> None:
        if self.current_track_id is None:
            logger.debug('ConsumerInRoom._handle_stop_broadcast: error - current_track_id is None')
            return
        room_slug = data['room_slug']
        await BroadcastRedisStore.save_broadcast_state(self.room_id, {'is_playing': 'false', 'track_id': 'none'})
        await move_room_track_to_voting_zone(self.current_track_id, self.room_id)
        self.current_track_id = None
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'stop_broadcast',
                'action': 'stop_broadcast',
                'room_slug': room_slug,
                'username': self.scope['user'].username,
            }
        )

    async def heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(5)
                if not self.scope['user'].is_authenticated:
                    break
                state = await BroadcastRedisStore.get_state(self.room_id)
                if not state or state.get('track_id') == 'none':
                    break
                current_time = float(state.get('current_time', 0))
                last_update = int(state.get('last_update', 0))
                is_playing = state.get('is_playing') == 'true'
                if last_update > 0:
                    elapsed = (int(time() * 1000) - last_update) / 1000
                    actual_time = current_time + elapsed
                else:
                    actual_time = current_time
                logger.debug(
                    msg=f'sync_state from heartbeat_loop: current_time: {actual_time}, server_timestamp: {int(time() * 1000)}, is_playing: {is_playing}')
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'sync_time',
                        'action': 'sync_time',
                        'current_time': actual_time,
                        'server_timestamp': int(time() * 1000),
                        'is_playing': is_playing,
                    }
                )
        except asyncio.CancelledError:
            return
        except (WebSocketClosedError, ConnectionClosed, ConnectionResetError) as e:
            logger.error(f'Error in connection: {e}')
            return
        except Exception as e:
            logger.error(f'Heartbeat error: {e}')
            return

    #TODO: Need method on_track_ended

    async def send_vote_update(self, event: dict):
        await self.send(text_data=json.dumps({
            'room_track_id': event['room_track_id'],
            'new_votes_count': event['new_votes_count'],
            'action': event['action'],
            'new_order': event['new_order'],
        }))

    async def delete_track(self, event: dict):
        await self.send(text_data=json.dumps({**event}))

    async def start_broadcast(self, event: dict):
        await self.send(text_data=json.dumps({**event}))

    async def sync_broadcast(self, event: dict):
        await self.send(text_data=json.dumps({**event}))

    async def sync_time(self, event: dict):
        await self.send(text_data=json.dumps({**event}))

    async def pause_broadcast(self, event: dict):
        await self.send(text_data=json.dumps({
            'action': 'pause_broadcast',
            'paused_by': event.get('username', 'System'),
            'room': event.get('room_slug', self.room_slug)
        }))

    async def stop_broadcast(self, event: dict):
        await self.send(text_data=json.dumps({
            'action': 'stop_broadcast',
            'stopped_by': event.get('username', 'System'),
            'room': event['room_slug']
        }))

    async def resume_broadcast(self, event: dict):
        await self.send(text_data=json.dumps({
            'action': 'resume_broadcast',
            'room': event.get('room_slug', self.room_slug),
            'resumed_by': event.get('username', 'System'),
        }))

    async def chat_message(self, event: dict):
        await self.send(text_data=json.dumps({
            'action': 'chat_message',
            'username': event['username'],
            'message': event['message'],
            'timestamp': event['timestamp'],
            'avatar_url': event.get('avatar_url', settings.DEFAULT_AVATAR_URL_REL)
        }))
