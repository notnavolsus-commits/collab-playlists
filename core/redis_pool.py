import redis.asyncio as redis
from django.conf import settings

class RedisConnectionPool:
    _pools: dict[int, redis.ConnectionPool] = {}

    @classmethod
    def get_redis_connections(cls, db):
        if db not in cls._pools:
            cls._pools[db] = redis.ConnectionPool(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=db,
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=5,
            )
        return cls._pools[db]

    @classmethod
    async def close_all_connections(cls):
        for pool in cls._pools.values():
            await pool.disconnect()