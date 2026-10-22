from django.conf import settings
from .stores import ChatRedisStore, BroadcastRedisStore
import json
from datetime import datetime
from .db import *


class ChatService:
    def __init__(self, room_group_name: str, channel_layer):
        self.room_group_name = room_group_name
        self.channel_layer = channel_layer

    @staticmethod
    async def get_chat_history_from_redis(room_id: int, limit: int = 50) -> list:
        try:
            messages = await ChatRedisStore.history(room_id, limit)
            result = []
            for msg in messages:
                data = json.loads(msg)
                username = data.get('username')
                avatar_url = settings.DEFAULT_AVATAR_URL_REL
                if username:
                    try:
                        user = await get_user_by_username(username)
                        if user:
                            avatar_url = await get_user_avatar(user)
                    except Exception as e:
                        print(f'Error in receiving avatar for {username}: ', e)
                result.append({**data, 'avatar_url': avatar_url})
            return result[::-1]
        except Exception as e:
            print(f'Error in Redis: func get_chat_history_from_redis - {e}')
            return []

    @staticmethod
    async def get_history_chat(room_id: int, limit: int = 50) -> list:
        if limit < 1: return []
        messages = await ChatService.get_chat_history_from_redis(room_id, limit)
        if not messages:
            messages = await get_chat_history_from_db(room_id, limit)
        return messages

    async def chat_message(self, data: dict[str, str], user, room_slug: str) -> None:
        user = user if user.is_authenticated else None
        username = user.username if user else 'Anonymous'
        avatar_url = await get_user_avatar(user) if user else settings.DEFAULT_AVATAR_URL_REL
        message = data.get('message')[:500]
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        room = await get_room_by_slug(room_slug)
        try:
            await save_message_to_db(room=room, message=message, user=user, timestamp=timestamp)
            message_data = {
                'username': username,
                'message': message,
                'timestamp': timestamp,
            }
            await ChatRedisStore.save_message_to_redis(room.id, message_data)
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
        except Exception as e:
            print('Error while saving data to db (chat_message): ', e)
            raise e


class BroadcastService:
    def __init__(self, room_group_name, channel_layer):
        self.room_group_name = room_group_name
        self.channel_layer = channel_layer

    async def set_playing(self, action: str, room_id: int, username: str) -> None:
        """Обрабатываем pause, resume"""
        state = await BroadcastRedisStore.get_state(room_id)
        if not state or state['track_id'] == 'none':
            raise ValueError('Room state are need for set_playing')
        redis_msg = {}
        if action == 'pause':
            redis_msg['is_playing'] = 'false'
        elif action == 'resume':
            redis_msg['is_playing'] = 'true'
        else:
            raise ValueError('Unknown action: ', action)
        group_msg = {'username': username,
                     'type': f'{action}_broadcast',
                     'action': f'{action}_broadcast', }
        await BroadcastRedisStore.save_broadcast_state(room_id, redis_msg)
        await self.channel_layer.group_send(self.room_group_name, group_msg)
