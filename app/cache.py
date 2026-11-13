import time
from threading import RLock
from functools import wraps


class MemoryCache:
    """Thread-safe, high-performance in-memory cache with TTL support."""
    def __init__(self):
        self._data = {}
        self._lock = RLock()

    def get(self, key):
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            val, expiry = item
            if expiry and time.time() > expiry:
                del self._data[key]
                return None
            return val

    def set(self, key, value, timeout=60):
        with self._lock:
            expiry = time.time() + timeout if timeout else None
            self._data[key] = (value, expiry)

    def delete(self, key):
        with self._lock:
            self._data.pop(key, None)

    def clear(self, prefix=None):
        """Clear all keys or all keys starting with prefix."""
        with self._lock:
            if not prefix:
                self._data.clear()
            else:
                keys_to_del = [k for k in self._data if k.startswith(prefix)]
                for k in keys_to_del:
                    self._data.pop(k, None)

    def cached(self, timeout=60, prefix='view'):
        """Decorator to cache function results."""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                key = f"{prefix}:{f.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
                cached_val = self.get(key)
                if cached_val is not None:
                    return cached_val
                result = f(*args, **kwargs)
                self.set(key, result, timeout=timeout)
                return result
            return decorated_function
        return decorator


cache = MemoryCache()

