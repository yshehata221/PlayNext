import time

from app.services.cache import TTLCache, cached


def test_cache_returns_stored_values_until_they_expire():
    calls = []

    @cached(ttl=1)
    def fetch(x):
        calls.append(x)
        return x * 2

    assert fetch(2) == 4
    assert fetch(2) == 4
    assert calls == [2]          # second call served from cache

    time.sleep(1.1)
    assert fetch(2) == 4
    assert calls == [2, 2]       # expired, so fetched again


def test_cache_distinguishes_arguments():
    @cached(ttl=60)
    def fetch(a, b=1):
        return (a, b)

    assert fetch(1) == (1, 1)
    assert fetch(1, b=2) == (1, 2)
    assert fetch.cache.misses == 2


def test_cache_evicts_rather_than_growing_forever():
    from app.services import cache as mod

    c = TTLCache(ttl=60)
    for i in range(mod.MAX_ENTRIES + 10):
        c.set(i, i)
    assert len(c._data) <= mod.MAX_ENTRIES


def test_cache_handles_list_arguments():
    """Batch lookups pass lists, which aren't hashable as-is."""
    calls = []

    @cached(ttl=60)
    def fetch(ids, where=None):
        calls.append(1)
        return len(ids)

    assert fetch([1, 2, 3]) == 3
    assert fetch([1, 2, 3]) == 3
    assert len(calls) == 1
    assert fetch([1, 2, 3], where=["a", "b"]) == 3   # different kwargs, new entry
    assert len(calls) == 2
