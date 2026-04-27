"""TTL cache wrapper using cachetools."""
import time
from cachetools import TTLCache
from functools import wraps

# Per-function caches
_caches = {}


def ttl_cache(ttl: int = 300, maxsize: int = 100):
    """Decorator: cache async function result by args+kwargs for ttl seconds.

    Tracks hit/miss for meta reporting.
    """
    def decorator(fn):
        cache = TTLCache(maxsize=maxsize, ttl=ttl)
        _caches[fn.__name__] = cache

        @wraps(fn)
        async def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in cache:
                result, cached_at = cache[key]
                wrapper.last_hit = True
                wrapper.last_query_ms = 0
                return result
            t0 = time.time()
            result = await fn(*args, **kwargs)
            elapsed_ms = int((time.time() - t0) * 1000)
            cache[key] = (result, now)
            wrapper.last_hit = False
            wrapper.last_query_ms = elapsed_ms
            return result

        wrapper.last_hit = False
        wrapper.last_query_ms = 0
        wrapper.cache_clear = cache.clear
        return wrapper
    return decorator


def clear_all_caches():
    """Invalidate all cached entries (for admin use)."""
    for cache in _caches.values():
        cache.clear()


def cache_stats():
    """Return current cache size for each function."""
    return {name: len(cache) for name, cache in _caches.items()}
