"""
Tiny TTL cache for third-party lookups.

Steam and IGDB both rate-limit (IGDB at roughly four requests a second), and the
same handful of games gets looked up repeatedly - a browse page, then its detail
page, then a similar-games row. Caching responses for a few minutes cuts that
to one call and keeps pages responsive.

In-process and bounded, so it suits a single instance. For several workers this
should become Redis; the interface is deliberately small enough to swap.
"""
import time
from functools import wraps
from typing import Any, Callable

MAX_ENTRIES = 2_000


class TTLCache:
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._data: dict[Any, tuple[float, Any]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: Any) -> Any | None:
        found = self._data.get(key)
        if found is None:
            self.misses += 1
            return None
        expires, value = found
        if expires < time.time():
            del self._data[key]
            self.misses += 1
            return None
        self.hits += 1
        return value

    def set(self, key: Any, value: Any) -> None:
        if len(self._data) >= MAX_ENTRIES:
            # drop the soonest-to-expire entries rather than tracking usage
            for k, _ in sorted(self._data.items(), key=lambda kv: kv[1][0])[: MAX_ENTRIES // 4]:
                self._data.pop(k, None)
        self._data[key] = (time.time() + self.ttl, value)

    def clear(self) -> None:
        self._data.clear()


def _hashable(value: Any) -> Any:
    """
    Arguments become part of the cache key, and some of ours are lists (a batch
    of app ids, a list of query clauses). Convert them to tuples so they can be
    hashed; anything else exotic falls back to its repr.
    """
    if isinstance(value, (list, set)):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


def cached(ttl: int = 300) -> Callable:
    """
    Memoise a function on its arguments for `ttl` seconds. A None or empty
    result is cached too - a game with no trailers shouldn't be asked about
    again every time someone opens its page.
    """
    cache = TTLCache(ttl)

    def decorate(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (_hashable(args), _hashable(kwargs))
            hit = cache.get(key)
            if hit is not None:
                return hit
            value = fn(*args, **kwargs)
            cache.set(key, value)
            return value

        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorate
