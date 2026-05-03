import copy
import threading
from datetime import datetime, timedelta

_CACHE_LOCK = threading.Lock()
_READ_CACHE = {}
_DEFAULT_TTL = timedelta(seconds=30)


def cached_read(key, loader, ttl: timedelta = _DEFAULT_TTL):
    now = datetime.utcnow()
    with _CACHE_LOCK:
        cached = _READ_CACHE.get(key)
        if cached and cached["expires_at"] > now:
            return copy.deepcopy(cached["value"])

    value = loader()
    with _CACHE_LOCK:
        _READ_CACHE[key] = {
            "expires_at": now + ttl,
            "value": copy.deepcopy(value),
        }
    return value


def invalidate_read_cache(prefix=None):
    with _CACHE_LOCK:
        if prefix is None:
            _READ_CACHE.clear()
            return
        keys_to_delete = [key for key in _READ_CACHE if str(key).startswith(str(prefix))]
        for key in keys_to_delete:
            _READ_CACHE.pop(key, None)


def read_cache_stats():
    with _CACHE_LOCK:
        return {"entries": len(_READ_CACHE)}
