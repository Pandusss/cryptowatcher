import redis.asyncio as redis
import logging
from typing import Optional
from app.core.config import settings

redis_client: Optional[redis.Redis] = None
_redis_available: bool = True
logger = logging.getLogger("RedisClient")



async def get_redis() -> Optional[redis.Redis]:
    global redis_client, _redis_available
    
    if not _redis_available:
        return None
    
    if redis_client is None:
        try:
            redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis is unavailable: {e}. Continue to work without Redis caching")
            _redis_available = False
            redis_client = None
            return None
    
    return redis_client


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None

