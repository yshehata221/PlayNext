"""
Shared rate limiter. It lives in its own module so routers can decorate
endpoints without importing `main` (which imports the routers - a cycle).

The default backend is in-process memory, which is right for a single instance.
Running more than one worker means each gets its own counters; point slowapi at
Redis (`storage_uri`) if this ever scales horizontally.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
