import time
import redis.asyncio as redis
import logging
from typing import Optional
from app.core.config import settings

redis_client: Optional[redis.Redis] = None
_retry_count: int = 0
_next_retry_time: float = 0
logger = logging.getLogger(__name__)


async def get_redis() -> Optional[redis.Redis]:
    global redis_client, _retry_count, _next_retry_time

    if redis_client is not None:
        return redis_client

    # Respect backoff delay between retries
    now = time.monotonic()
    if _retry_count > 0 and now < _next_retry_time:
        return None

    try:
        redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
        )
        await redis_client.ping()
        if _retry_count > 0:
            logger.info(f"Redis connection restored after {_retry_count} retries")
        _retry_count = 0
        _next_retry_time = 0
        return redis_client
    except Exception as e:
        _retry_count += 1
        delay = min(2 ** _retry_count, 300)
        _next_retry_time = time.monotonic() + delay
        logger.warning(
            f"Redis is unavailable: {e}. "
            f"Retry #{_retry_count} in {delay}s. Continuing without cache."
        )
        redis_client = None
        return None


async def reset_redis():
    """Reset connection so next get_redis() retries immediately."""
    global redis_client
    if redis_client:
        try:
            await redis_client.close()
        except Exception:
            pass
    redis_client = None


async def close_redis():
    global redis_client, _retry_count, _next_retry_time
    if redis_client:
        await redis_client.close()
        redis_client = None
    _retry_count = 0
    _next_retry_time = 0
