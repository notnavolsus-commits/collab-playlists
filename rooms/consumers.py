import json
import redis.asyncio as redis
import asyncio
from django.conf import settings
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Count
from django.contrib.auth.models import User

from .models import Room, RoomTrack, Vote, ChatMessage
from datetime import datetime
from time import time


def get_redis_client(db):
    return redis.Redis(
        host=getattr(settings, 'REDIS_HOST', 'localhost'),
        port=getattr(settings, 'REDIS_PORT', 6379),
        db=db,
        decode_responses=True,
    )


redis_client_chat = get_redis_client(db=getattr(settings, 'REDIS_DB_CHAT', 1))
redis_client_broadcast = get_redis_client(db=getattr(settings, 'REDIS_DB_BROADCAST', 2))


class ConsumerInRoom(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_slug = self.scope['url_route']['kwargs']['room_slug']
        self.room_group_name = f'room_{self.room_slug}'
        self.is_creator = None
        self.heartbeat_task = False
        try:
            room = await self.get_room_by_slug(room_slug=self.room_slug)
            self.room_id = room.id
        except Room.DoesNotExist:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        self.is_creator = await self.room_creator_validation(room, self.scope['user'])

        if self.is_creator:
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        history = await self.get_history_chat(room_id=room.id)
        for msg in history:
            await self.send(text_data=json.dumps({
                'action': 'chat_history',
                'username': msg['username'],
                'message': msg['message'],
                'timestamp': msg['timestamp'],
                'avatar_url': str(msg['avatar_url']),
            }))

        try:
            state = await redis_client_broadcast.hgetall(f'room_id:{room.id}')
        except Exception as e:
            print('Ошибка в сохранении данных в Redis при записи состояние в базу эфира', e)
            state = None
        if state and state.get('track_id') != 'none':
            await self.send(text_data=json.dumps({
                'action': 'sync_state',
                'track_id': int(state['track_id']),
                'current_time': float(state['current_time']),
                'is_playing': state.get('is_playing') == 'true',
                'started_by': state.get('started_by', ''),
                'last_update': int(state.get('last_update', 0)),
            }))

    async def disconnect(self, close_code):
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data['action']

        action_handlers = {
            'vote': self._handle_vote,
            'start_broadcast': self._handle_start_broadcast,
            'sync_broadcast': self._handle_sync_broadcast,
            'pause_broadcast': self._handle_pause_broadcast,
            'resume_broadcast': self._handle_resume_broadcast,
            'stop_broadcast': self._handle_stop_broadcast,
            'chat_message': self._handle_chat_message,
        }

        handler = action_handlers.get(action)
        if handler:
            await handler(data)

    async def _save_broadcast_state(self, mapping):
        key = f'room_id:{self.room_id}'
        last_update = int(time() * 1000)
        mapping = {'last_update': str(last_update), **mapping}
        try:
            await redis_client_broadcast.hset(key, mapping=mapping)
            await redis_client_broadcast.expire(key, 3600)
        except Exception as e:
            print(f'Ошибка сохранения состояния в Redis: {e}')
        return last_update

    async def _handle_vote(self, data):
        if not self.scope['user'].is_authenticated: return
        toggle_dict = await self.toggle_vote(self.scope['user'].id, data['room_track_id'])
        if toggle_dict:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_vote_update',
                    **toggle_dict
                }
            )

    async def _handle_start_broadcast(self, data):
        room_track_id = data['track_id']
        user = self.scope['user']
        if self.is_creator:
            try:
                await self._save_broadcast_state({'track_id': str(room_track_id),
                                                  'current_time': '0',
                                                  'is_playing': 'true',
                                                  'started_by': user.username,
                                                  'room_slug': self.room_slug})
            except Exception as e:
                print('Ошибка в сохранении данных в Redis при старте эфира: ', e)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'start_broadcast',
                    'action': 'start_broadcast',
                    'track_id': room_track_id,
                }
            )

    async def _handle_generic_broadcast(self, action, data):
        """Обрабатываем sync, pause, resume"""
        current_time = data['current_time']
        if self.is_creator:
            redis_msg = {'current_time': str(current_time)}
            group_msg = {
                'type': None,
                'action': None,
                'current_time': current_time,
            }
            if action == 'pause':
                redis_msg.update({'is_playing': 'false'})
            elif action == 'resume':
                redis_msg.update({'is_playing': 'true'})
            last_update = await self._save_broadcast_state(redis_msg)
            group_msg.update({'server_timestamp': last_update})
            if action == 'sync':
                group_msg['type'] = group_msg['action'] = 'sync_broadcast'
            elif action in ('pause', 'resume'):
                group_msg.update({'username': self.scope['user'].username})
                if action == 'pause':
                    group_msg['type'] = group_msg['action'] = 'pause_broadcast'
                elif action == 'resume':
                    group_msg['type'] = group_msg['action'] = 'resume_broadcast'
            await self.channel_layer.group_send(self.room_group_name, group_msg)

    async def _handle_sync_broadcast(self, data):
        await self._handle_generic_broadcast('sync', data)

    async def _handle_pause_broadcast(self, data):
        await self._handle_generic_broadcast('pause', data)

    async def _handle_resume_broadcast(self, data):
        await self._handle_generic_broadcast('resume', data)

    async def _handle_stop_broadcast(self, data):
        room_slug = data['room_slug']
        if self.is_creator:
            await self._save_broadcast_state({'is_playing': 'false', 'track_id': 'none'})
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'stop_broadcast',
                    'action': 'stop_broadcast',
                    'room_slug': room_slug,
                    'username': self.scope['user'].username,
                }
            )

    async def _handle_chat_message(self, data):
        user = self.scope['user']
        username = user.username if user.is_authenticated else 'Аноним'
        avatar_url = await self.get_user_avatar(user) if user.is_authenticated else settings.DEFAULT_AVATAR_URL
        if not user.is_authenticated:
            user = None
        message = data['message'][:500]
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        room = await self.get_room_by_slug(self.room_slug)
        try:
            await self.save_message_to_db(room=room, user=user, username=username, message=message)
            message_data = {
                'username': username,
                'message': message,
                'timestamp': timestamp,
            }
            await self.save_message_to_redis(room.id, message_data)
        except Exception as e:
            print('Ошибка в сохранении в базу данных сообщения (chat_message): ', e)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'action': 'chat_message',
                'username': username,
                'message': message,
                'timestamp': timestamp,
                'avatar_url': avatar_url,
            }
        )

    @database_sync_to_async
    def room_creator_validation(self, room, user):
        if room.created_by == user:
            return True
        else:
            return False

    @database_sync_to_async
    def get_room_by_slug(self, room_slug):
        return Room.objects.get(slug=room_slug)

    @database_sync_to_async
    def get_user_by_username(self, username):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def toggle_vote(self, user_id, room_track_id):
        try:
            room_track = RoomTrack.objects.get(id=room_track_id)
        except RoomTrack.DoesNotExist:
            return
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return
        vote = Vote.objects.filter(user=user, room_track=room_track)
        if vote.exists():
            vote.delete()
            action = 'unvoted'
        else:
            Vote.objects.create(user=user, room_track=room_track)
            action = 'voted'
        new_votes_count = Vote.objects.filter(room_track=room_track).count()
        room = room_track.room
        room_tracks = RoomTrack.objects.filter(room=room).annotate(vote_count=Count('votes')).order_by('-vote_count',
                                                                                                       'created_at')
        new_order = list(room_tracks.values_list('id', flat=True))
        return {
            'new_votes_count': new_votes_count,
            'action': action,
            'room_track_id': room_track_id,
            'new_order': new_order,
        }

    @database_sync_to_async
    def save_message_to_db(self, room, user, username, message):
        ChatMessage.objects.create(room=room, user=user, username=username, message=message[:500])

    @database_sync_to_async
    def get_chat_history_from_db(self, room_id, limit):
        qs = ChatMessage.objects.filter(room=room_id).order_by('-created_at')[:limit]
        return [
            {
                'username': msg.username,
                'message': msg.message,
                'timestamp': msg.formatted_timestamp,
                'avatar_url': msg.avatar_url,
            }
            for msg in reversed(qs)
        ]

    @database_sync_to_async
    def get_user_avatar(self, user):
        if user.is_authenticated and hasattr(user, 'profile'):
            return user.profile.get_avatar_url()
        return settings.DEFAULT_AVATAR_URL

    async def heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(5)
                if not self.scope['user'].is_authenticated:
                    break

                key = f'room_id:{self.room_id}'
                state = await redis_client_broadcast.hgetall(key)
                if not state or state.get('track_id') == 'none':
                    break
                current_time = float(state.get('current_time', 0))
                last_update = int(state.get('last_update', 0))
                is_playing = state.get('is_playing') == 'true'
                if is_playing and last_update > 0:
                    elapsed = (int(time() * 1000) - last_update) / 1000
                    actual_time = current_time + elapsed
                else:
                    actual_time = current_time
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'sync_time',
                        'current_time': actual_time,
                        'server_timestamp': int(time() * 1000),
                        'is_playing': is_playing,
                    }
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f'Heartbeat error: {e}')

    async def send_vote_update(self, event):
        await self.send(text_data=json.dumps({
            'room_track_id': event['room_track_id'],
            'new_votes_count': event['new_votes_count'],
            'action': event['action'],
            'new_order': event['new_order'],
        }))

    async def delete_track(self, event):
        await self.send(text_data=json.dumps({**event}))

    async def start_broadcast(self, event):
        await self.send(text_data=json.dumps({**event}))

    async def sync_broadcast(self, event):
        await self.send(text_data=json.dumps({**event}))

    async def sync_time(self, event):
        await self.send(text_data=json.dumps({**event}))

    async def pause_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'action': 'pause_broadcast',
            'current_time': event['current_time'],
            'server_timestamp': event.get('server_timestamp'),
            'paused_by': event.get('username', 'System'),
            'room': event.get('room_slug', self.room_slug)
        }))

    async def stop_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'action': 'stop_broadcast',
            'stopped_by': event.get('username', 'System'),
            'room': event['room_slug']
        }))

    async def resume_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'action': 'resume_broadcast',
            'room': event.get('room_slug', self.room_slug),
            'current_time': event['current_time'],
            'server_timestamp': event.get('server_timestamp'),
            'resumed_by': event.get('username', 'System'),
        }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'action': 'chat_message',
            'username': event['username'],
            'message': event['message'],
            'timestamp': event['timestamp'],
            'avatar_url': event.get('avatar_url', settings.DEFAULT_AVATAR_URL)
        }))

    async def get_history_chat(self, room_id, limit=50):
        messages = await self.get_chat_history_from_redis(room_id, limit)
        if not messages:
            messages = await self.get_chat_history_from_db(room_id, limit)
        return messages

    async def save_message_to_redis(self, room_id, message_data):
        key = f'chat:room:{room_id}'
        CHAT_HISTORY_LIMIT = getattr(settings, 'CHAT_HISTORY_LIMIT', 100)

        try:
            await redis_client_chat.lpush(key, json.dumps(message_data, ensure_ascii=False))
            await redis_client_chat.ltrim(key, 0, CHAT_HISTORY_LIMIT - 1)
        except Exception as e:
            print(f'Ошибка в Redis: func save_message_to_redis - {e}')

    async def get_chat_history_from_redis(self, room_id, limit=50):
        key = f'chat:room:{room_id}'

        try:
            messages = await redis_client_chat.lrange(key, 0, limit - 1)
            result = []
            for msg in messages:
                data = json.loads(msg)
                username = data.get('username')
                avatar_url = settings.DEFAULT_AVATAR_URL
                if username and username != 'Аноним':
                    try:
                        user = await self.get_user_by_username(username)
                        if user:
                            avatar_url = await self.get_user_avatar(user)
                    except Exception as e:
                        print(f'Ошибка в получении аватара для {username}: ', e)
                result.append({**data, 'avatar_url': avatar_url})
            return result
        except Exception as e:
            print(f'Ошибка в Redis: func get_chat_history_from_redis - {e}')
            return []



