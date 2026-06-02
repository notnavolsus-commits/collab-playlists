import json
import redis
from django.conf import settings
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, RoomTrack, Vote, ChatMessage
from django.contrib.auth.models import User
from django.db.models import Count
from datetime import datetime


class ConsumerInRoom(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_slug = self.scope['url_route']['kwargs']['room_slug']
        self.room_group_name = f'room_{self.room_slug}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        room = await self.get_room_by_slug(room_slug=self.room_slug)
        history = await self.get_history_chat(room_id=room.id)
        for msg in history:
            await self.send(text_data=json.dumps({
                'action': 'chat_history',
                'username': msg['username'],
                'message': msg['message'],
                'timestamp': msg['timestamp'],
            }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data['action'] == 'vote':
            room_track_id = data['room_track_id']
            if self.scope['user'].is_authenticated:
                user_id = self.scope['user'].id
            else:
                return
            toggle_dict = await self.toggle_vote(user_id, room_track_id)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_vote_update',
                    **toggle_dict
                }
            )
        elif data['action'] == 'start_broadcast':
            room_track_id = data['track_id']
            user = self.scope['user']
            room = await self.get_room_by_room_track(room_track_id)
            if await self.room_creator_validation(room, user):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'start_broadcast',
                        'action': 'start_broadcast',
                        'track_id': room_track_id,
                    }
                )
        elif data['action'] == 'sync_broadcast':
            room_track_id = data['track_id']
            user = self.scope['user']
            room = await self.get_room_by_room_track(room_track_id)
            if await self.room_creator_validation(room, user):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'sync_broadcast',
                        'action': 'sync_broadcast',
                        'track_id': room_track_id,
                        'current_time': data['current_time']
                    }
                )
        elif data['action'] == 'stop_broadcast':
            room_slug = data['room_slug']
            room = await self.get_room_by_slug(room_slug)
            if await self.room_creator_validation(room, self.scope['user']):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'stop_broadcast',
                        'action': 'stop_broadcast',
                        'room_slug': room_slug
                    }
                )
        elif data['action'] == 'chat_message':
            user = self.scope['user']
            username = user.username if user.is_authenticated else 'Аноним'
            if not user.is_authenticated: user = None
            message = data['message'][:500]
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            room = await self.get_room_by_slug(self.room_slug)

            await self.save_message_to_db(room=room, user=user, username=username, message=message)

            message_data = {
                'username': username,
                'message': message,
                'timestamp': timestamp,
            }

            save_message_to_redis(room.id, message_data)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'action': 'chat_message',
                    'username': username,
                    'message': message,
                    'timestamp': timestamp,
                }
            )

    @database_sync_to_async
    def room_creator_validation(self, room, user):
        if room.created_by == user:
            return True
        else:
            return False

    @database_sync_to_async
    def get_room_by_room_track(self, track_id):
        room_track = RoomTrack.objects.select_related('track', 'room').get(id=track_id)
        room = room_track.room
        return room

    @database_sync_to_async
    def get_room_by_slug(self, room_slug):
        return Room.objects.get(slug=room_slug)

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
    def get_username_by_user(self, user):
        if user.is_authenticated:
            return user.username
        else:
            return None

    @database_sync_to_async
    def get_chat_history_from_db(self, room_id, limit):
        qs = ChatMessage.objects.filter(room=room_id).order_by('-created_at')[:limit]
        return [
            {
                'username': msg.username,
                'message': msg.message,
                'timestamp': msg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
            for msg in reversed(qs)
        ]

    async def send_vote_update(self, event):
        await self.send(text_data=json.dumps({
            'room_track_id': event['room_track_id'],
            'new_votes_count': event['new_votes_count'],
            'action': event['action'],
            'new_order': event['new_order'],
        }))

    async def delete_track(self, event):
        await self.send(text_data=json.dumps({
            'action': 'delete_track',
            'track_id': event['track_id'],
        }))

    async def start_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'action': 'start_broadcast',
            'track_id': event['track_id'],
        }))

    async def sync_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'action': 'sync_broadcast',
            'track_id': event['track_id'],
            'current_time': event['current_time'],
        }))

    async def stop_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'action': 'stop_broadcast',
            'room': event['room_slug']
        }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'action': 'chat_message',
            'username': event['username'],
            'message': event['message'],
            'timestamp': event['timestamp'],
        }))

    async def get_history_chat(self, room_id, limit=50):
        messages = get_chat_history_from_redis(room_id, limit)
        if not messages:
            messages = await self.get_chat_history_from_db(room_id, limit)
        return messages


redis_client = redis.Redis(
    host=getattr(settings, 'REDIS_HOST', 'localhost'),
    port=getattr(settings, 'REDIS_PORT', 6379),
    db=getattr(settings, 'REDIS_DB_CHAT', 1),
    decode_responses=True,
)


def save_message_to_redis(room_id, message_data):
    key = f'chat:room:{room_id}'
    CHAT_HISTORY_LIMIT = getattr(settings, 'CHAT_HISTORY_LIMIT', 100)

    try:
        redis_client.lpush(key, json.dumps(message_data, ensure_ascii=False))
        redis_client.ltrim(key, 0, CHAT_HISTORY_LIMIT - 1)
    except Exception as e:
        print(f'Ошибка в Redis: func save_message_to_redis - {e}')


def get_chat_history_from_redis(room_id, limit=50):
    key = f'chat:room:{room_id}'

    try:
        messages = redis_client.lrange(key, 0, limit - 1)
        return [json.loads(msg) for msg in messages]
    except Exception as e:
        print(f'Ошибка в Redis: func get_chat_history_from_redis - {e}')
        return []
