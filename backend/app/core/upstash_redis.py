import os

from upstash_redis.asyncio import Redis

_redis_client: Redis | None = None


def get_upstash_redis_client() -> Redis | None:
    """Create one shared Upstash Redis REST client per worker/process."""
    global _redis_client

    url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if not url or not token:
        return None

    if _redis_client is None:
        _redis_client = Redis.from_env()
    return _redis_client
