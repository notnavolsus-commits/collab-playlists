from time import time
import redis.asyncio as redis
from core.redis_pool import RedisConnectionPool
from django.conf import settings
from json import dumps

_chat_pool = RedisConnectionPool.get_redis_connections(db=getattr(settings, 'REDIS_DB_CHAT', 1))
# _chat_pool = RedisConnectionPool.get_redis_connections(db=3)
redis_chat_client = redis.Redis(connection_pool=_chat_pool)
_broadcast_pool = RedisConnectionPool.get_redis_connections(db=getattr(settings, 'REDIS_DB_BROADCAST', 2))
# _broadcast_pool = RedisConnectionPool.get_redis_connections(db=4)
redis_broadcast_client = redis.Redis(connection_pool=_broadcast_pool)


class ChatRedisStore:
    CHAT_HISTORY_LIMIT = getattr(settings, 'CHAT_HISTORY_LIMIT', 100)
    key_format = 'chat:room:{room_id}'

    @staticmethod
    async def save_message_to_redis(room_id: int, message_data: dict) -> None:
        key = ChatRedisStore.key_format.format(room_id=room_id)

        try:
            await redis_chat_client.lpush(key, dumps(message_data, ensure_ascii=False))
            await redis_chat_client.ltrim(key, 0, ChatRedisStore.CHAT_HISTORY_LIMIT - 1)
        except Exception as e:
            print(f'Error in Redis: func save_message_to_redis - {e}')

    @staticmethod
    async def history(room_id, limit=50):
        key = ChatRedisStore.key_format.format(room_id=room_id)

        try:
            messages = await redis_chat_client.lrange(key, 0, limit - 1)
            return messages
        except Exception as e:
            print(f'Error in Redis: func history from redis - {e}')
            return []

    @staticmethod
    async def delete_history(room_id):
        key = ChatRedisStore.key_format.format(room_id=room_id)

        try:
            await redis_chat_client.delete(key)
        except Exception as e:
            print(f'Error in Redis deletion history = {e}')
            raise e


class BroadcastRedisStore:
    key_format = 'room_id:{room_id}'

    @staticmethod
    async def save_broadcast_state(room_id: int, mapping) -> int:
        key = BroadcastRedisStore.key_format.format(room_id=room_id)
        last_update = int(time() * 1000)
        mapping = {'last_update': str(last_update), **mapping}
        try:
            await redis_broadcast_client.hset(key, mapping=mapping)
            await redis_broadcast_client.expire(key, 3600)
        except Exception as e:
            print(f'Error in saving data to Redis: {e}')
        return last_update

    @staticmethod
    async def get_state(room_id: int):
        key = BroadcastRedisStore.key_format.format(room_id=room_id)
        try:
            state = await redis_broadcast_client.hgetall(key)
            return state
        except Exception as e:
            print(f'Error in get_state method in BroadcastRedisState: {e}')
            return {}

    @staticmethod
    async def clear_state(room_id: int):
        key = BroadcastRedisStore.key_format.format(room_id=room_id)
        try:
            await redis_broadcast_client.delete(key)
        except Exception as e:
            print(f'Error in clear_state method in BroadcastRedisState: {e}')
            raise e