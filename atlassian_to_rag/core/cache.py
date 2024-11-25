import pickle
from datetime import timedelta
from functools import lru_cache
from typing import Any, Callable, Optional

import redis


class CacheManager:
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url)

    def cache_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key from the arguments."""
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        return ":".join(key_parts)

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        value = self.redis_client.get(key)
        return pickle.loads(value) if value else None

    def set(self, key: str, value: Any, expire: timedelta = timedelta(hours=1)) -> None:
        """Set a value in cache with expiration."""
        self.redis_client.setex(key, expire, pickle.dumps(value))

    def delete(self, key: str) -> None:
        """Delete a value from cache."""
        self.redis_client.delete(key)


def cached(prefix: str, expire: timedelta = timedelta(hours=1)) -> Callable:
    """Decorator for caching function results."""

    def decorator(func: Callable) -> Callable:
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            if self.cache_manager is None:
                return func(self, *args, **kwargs)

            cache_key = self.cache_manager.cache_key(prefix, *args, **kwargs)
            result = self.cache_manager.get(cache_key)

            if result is None:
                result = func(self, *args, **kwargs)
                self.cache_manager.set(cache_key, result, expire)

            return result

        return wrapper

    return decorator
