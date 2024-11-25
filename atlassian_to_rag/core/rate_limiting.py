import time
from datetime import timedelta
from functools import wraps
from typing import Callable, Dict, Optional

import redis


class RateLimiter:
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url)

    def is_rate_limited(self, key: str, limit: int, window: timedelta) -> bool:
        """Check if the request should be rate limited."""
        current = int(time.time())
        window_seconds = int(window.total_seconds())

        pipeline = self.redis_client.pipeline()
        pipeline.zadd(key, {str(current): current})
        pipeline.zremrangebyscore(key, 0, current - window_seconds)
        pipeline.zcard(key)
        pipeline.expire(key, window_seconds)
        results = pipeline.execute()

        return results[2] > limit


def rate_limit(limit: int, window: timedelta, key_func: Optional[Callable] = None) -> Callable:
    """Decorator for rate limiting."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, "rate_limiter"):
                raise AttributeError("Class must have a rate_limiter attribute")

            key = f"rate_limit:{func.__name__}"
            if key_func:
                key = f"{key}:{key_func(*args, **kwargs)}"

            if self.rate_limiter.is_rate_limited(key, limit, window):
                raise Exception("Rate limit exceeded")

            return func(self, *args, **kwargs)

        return wrapper

    return decorator
