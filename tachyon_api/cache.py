"""
Cache utilities: decorator with TTL and pluggable backends.

This module provides:
- BaseCacheBackend protocol and an in-memory implementation
- CacheConfig dataclass and helpers to set global/app config
- cache decorator usable on any sync/async function (including routes)

Design notes:
- Default keys include a per-decoration namespace plus function and arguments
- Unless predicate allows opt-out per-call
- TTL can be provided per-decorator or falls back to global default
"""

from __future__ import annotations

import logging
import time
import inspect
import hashlib
import math
from uuid import uuid4

from starlette.concurrency import run_in_threadpool
from collections import OrderedDict
from threading import RLock
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger(__name__)


class BaseCacheBackend:
    """Synchronous cache backend interface; None means a cache miss.

    External implementations must support concurrent worker-thread calls. Async
    decorated functions offload backend I/O to Starlette's shared thread pool;
    coroutine-based clients are not supported by this synchronous interface.
    """

    def get(self, key: str) -> Any:  # pragma: no cover - interface
        raise NotImplementedError

    def set(
        self, key: str, value: Any, ttl: Optional[float] = None
    ) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def delete(self, key: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def clear(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryCacheBackend(BaseCacheBackend):
    """Thread-safe, bounded LRU cache with monotonic TTL expiration.

    Expired entries are removed on access or evicted under capacity pressure.
    Each write updates the LRU in constant time without scanning the cache.
    Non-positive TTLs retain the historical meaning of no expiration.
    """

    def __init__(self, max_entries: int = 1024) -> None:
        if not isinstance(max_entries, int) or max_entries <= 0:
            raise ValueError("max_entries must be a positive integer")
        self.max_entries = max_entries
        self._store: OrderedDict[str, Tuple[float | None, Any]] = OrderedDict()
        self._lock = RLock()

    def _is_expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and time.monotonic() >= expires_at

    def get(self, key: str) -> Any:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if self._is_expired(expires_at):
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            now = time.monotonic()
            expires_at = now + ttl if ttl is not None and ttl > 0 else None
            self._store[key] = (expires_at, value)
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


@dataclass
class CacheConfig:
    backend: BaseCacheBackend
    default_ttl: float = 60.0
    key_builder: Optional[Callable[[Callable, tuple, dict], str]] = None
    enabled: bool = True


_cache_config: Optional[CacheConfig] = None


def _default_key_builder(func: Callable, args: tuple, kwargs: dict) -> str:
    parts = [getattr(func, "__module__", ""), getattr(func, "__qualname__", ""), "|"]
    # Stable kwargs order
    items = [repr(a) for a in args] + [
        f"{k}={repr(v)}" for k, v in sorted(kwargs.items())
    ]
    raw_key = ":".join(parts + items)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def create_cache_config(
    backend: Optional[BaseCacheBackend] = None,
    default_ttl: float = 60.0,
    key_builder: Optional[Callable[[Callable, tuple, dict], str]] = None,
    enabled: bool = True,
) -> CacheConfig:
    """Create and set the global cache configuration.

    Returns the created CacheConfig and sets it as the active global config.
    """
    global _cache_config
    cfg = CacheConfig(
        backend=backend if backend is not None else InMemoryCacheBackend(),
        default_ttl=default_ttl,
        key_builder=key_builder,
        enabled=enabled,
    )
    _cache_config = cfg
    return cfg


def set_cache_config(config: CacheConfig) -> None:
    """Set the global cache configuration object."""
    global _cache_config
    _cache_config = config


def get_cache_config() -> CacheConfig:
    """Get the current cache configuration, creating a default one if missing."""
    global _cache_config
    if _cache_config is None:
        _cache_config = create_cache_config()
    return _cache_config


def cache(
    TTL: Optional[float] = None,
    *,
    key_builder: Optional[Callable[[Callable, tuple, dict], str]] = None,
    unless: Optional[Callable[[tuple, dict], bool]] = None,
    backend: Optional[BaseCacheBackend] = None,
    config: Optional[CacheConfig] = None,
):
    """Cache decorator with TTL and pluggable backend.

    Args:
        TTL: Time-to-live in seconds for this decorator instance. Falls back to config.default_ttl.
        key_builder: Optional custom function to build cache keys. Defaults use
            a random namespace per decoration; provide a stable builder to share
            entries across processes, restarts or distinct decorated functions.
        unless: Predicate receiving (args, kwargs). If returns True, skip cache for that call.
        backend: Optional backend override for this decorator.
        config: Explicit config for isolated apps. Otherwise the global config is
            captured at decoration time; replacing the global does not rebind it.
    """

    def decorator(func: Callable):
        cfg = config if config is not None else get_cache_config()
        be = backend if backend is not None else cfg.backend
        ttl_value = cfg.default_ttl if TTL is None else TTL
        kb = key_builder or cfg.key_builder
        if kb is None:
            namespace = uuid4().hex

            def kb(function, args, kwargs):
                return namespace + ":" + _default_key_builder(function, args, kwargs)

        if any(inspect.iscoroutinefunction(method) for method in (be.get, be.set)):
            raise TypeError("Cache backends require synchronous get/set methods")
        # Only the known bounded implementation can safely run inline. A subclass
        # may override these methods with blocking I/O, so it is offloaded too.
        inline_backend = type(be) is InMemoryCacheBackend

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not cfg.enabled or (unless and unless(args, kwargs)):
                    return await func(*args, **kwargs)
                key = kb(func, args, kwargs)
                try:
                    cached = be.get(key) if inline_backend else await run_in_threadpool(be.get, key)
                except Exception as exc:
                    logger.warning("Cache get failed for key %r: %s", key, exc)
                    cached = None
                if cached is not None:
                    return cached
                result = await func(*args, **kwargs)
                try:
                    if inline_backend:
                        be.set(key, result, ttl_value)
                    else:
                        await run_in_threadpool(be.set, key, result, ttl_value)
                except Exception as exc:
                    logger.warning("Cache set failed for key %r: %s", key, exc)
                return result

            return async_wrapper
        else:

            @wraps(func)
            def wrapper(*args, **kwargs):
                if not cfg.enabled or (unless and unless(args, kwargs)):
                    return func(*args, **kwargs)
                key = kb(func, args, kwargs)
                try:
                    cached = be.get(key)
                except Exception as exc:
                    logger.warning("Cache get failed for key %r: %s", key, exc)
                    cached = None
                if cached is not None:
                    return cached
                result = func(*args, **kwargs)
                try:
                    be.set(key, result, ttl_value)
                except Exception as exc:
                    logger.warning("Cache set failed for key %r: %s", key, exc)
                return result

            return wrapper

    return decorator


class RedisCacheBackend(BaseCacheBackend):
    """Adapter backend for Redis-like clients.

    Expects a client with .get(key) -> bytes|str|None and .set(key, value, ex=ttl_seconds).
    The stored values should be JSON-serializable or pickled externally by the user.
    """

    def __init__(self, client) -> None:
        self.client = client

    def get(self, key: str) -> Any:
        value = self.client.get(key)
        # Many clients return bytes; decode if possible
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except Exception:
                return value
        return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        # Use ex (expire seconds) if available
        kwargs = {}
        if ttl and ttl > 0:
            kwargs["ex"] = math.ceil(ttl)
        # Best effort set
        self.client.set(key, value, **kwargs)

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)
        except Exception as exc:
            logger.warning("Cache operation failed: %s", exc)

    def clear(self) -> None:
        # flushdb() clears the current Redis database only (not all databases).
        # Use with care in shared Redis instances.
        try:
            self.client.flushdb()
        except Exception as exc:
            logger.warning("Redis cache clear failed: %s", exc)


class MemcachedCacheBackend(BaseCacheBackend):
    """Adapter backend for Memcached-like clients.

    Expects a client with .get(key) and .set(key, value, expire=ttl_seconds).
    """

    def __init__(self, client) -> None:
        self.client = client

    def get(self, key: str) -> Any:
        return self.client.get(key)

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expire = math.ceil(ttl) if ttl and ttl > 0 else 0
        # Memcached interprets values above 30 days as absolute Unix time.
        if expire > 30 * 24 * 60 * 60:
            expire = math.ceil(time.time() + ttl)
        try:
            # pymemcache: set(key, value, expire=...)
            self.client.set(key, value, expire=expire)
        except TypeError:
            # python-binary-memcached: set(key, value, time=...)
            self.client.set(key, value, time=expire)

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)
        except Exception as exc:
            logger.warning("Cache operation failed: %s", exc)

    def clear(self) -> None:
        try:
            self.client.flush_all()
        except Exception as exc:
            logger.warning("Cache operation failed: %s", exc)
