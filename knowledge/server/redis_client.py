import redis.asyncio as redis
from .config import REDIS_HOST, REDIS_PORT, REDIS_DB

pool = redis.ConnectionPool(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
redis_client = redis.Redis(connection_pool=pool)


async def get_cache(key: str):
    return await redis_client.get(key)


async def set_cache(key: str, value: str, ttl: int = 300):
    await redis_client.set(key, value, ex=ttl)


async def del_cache(key: str):
    await redis_client.delete(key)
