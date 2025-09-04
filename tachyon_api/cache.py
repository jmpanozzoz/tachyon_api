"""
Cache utilities: decorator with TTL and pluggable backends.

This module provides:
- BaseCacheBackend protocol and an in-memory implementation
- CacheConfig dataclass and helpers to set global/app config
- cache decorator usable on any sync/async function (including routes)

Design notes:
- Key builder defaults to a stable representation of function + args/kwargs
- Unless predicate allows opt-out per-call
- TTL can be provided per-decorator or falls back to global default
"""

from __future__ import annotations

import time
import asyncio
import hashlib
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, Tuple


class BaseCacheBackend:
    """Minimal cache backend interface."""

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
    """Simple in-memory cache with TTL using wall-clock time."""

    def __init__(self) -> None:
        self._store: dict[str, Tuple[float | None, Any]] = {}

    def _is_expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and time.time() >= expires_at

    def get(self, key: str) -> Any:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if self._is_expired(expires_at):
            # Lazy expiration
            try:
                del self._store[key]
            except KeyError:
                pass
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expires_at = time.time() + ttl if ttl and ttl > 0 else None
        self._store[key] = (expires_at, value)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
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
        backend=backend or InMemoryCacheBackend(),
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
):
    """Cache decorator with TTL and pluggable backend.

    Args:
        TTL: Time-to-live in seconds for this decorator instance. Falls back to config.default_ttl.
        key_builder: Optional custom function to build cache keys.
        unless: Predicate receiving (args, kwargs). If returns True, skip cache for that call.
        backend: Optional backend override for this decorator.
    """

    def decorator(func: Callable):
        cfg = get_cache_config()
        be = backend or cfg.backend
        ttl_value = cfg.default_ttl if TTL is None else TTL
        kb = (
            key_builder
            or cfg.key_builder
            or (lambda f, a, kw: _default_key_builder(f, a, kw))
        )

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not cfg.enabled or (unless and unless(args, kwargs)):
                    return await func(*args, **kwargs)
                key = kb(func, args, kwargs)
                cached = be.get(key)
                if cached is not None:
                    return cached
                result = await func(*args, **kwargs)
                try:
                    be.set(key, result, ttl_value)
                except Exception:
                    # Backend errors should not break the app
                    pass
                return result

            return async_wrapper
        else:

            @wraps(func)
            def wrapper(*args, **kwargs):
                if not cfg.enabled or (unless and unless(args, kwargs)):
                    return func(*args, **kwargs)
                key = kb(func, args, kwargs)
                cached = be.get(key)
                if cached is not None:
                    return cached
                result = func(*args, **kwargs)
                try:
                    be.set(key, result, ttl_value)
                except Exception:
                    pass
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
            kwargs["ex"] = int(ttl)
        # Best effort set
        self.client.set(key, value, **kwargs)

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)
        except Exception:
            pass

    def clear(self) -> None:
        # Not standardized; no-op by default
        pass


class MemcachedCacheBackend(BaseCacheBackend):
    """Adapter backend for Memcached-like clients.

    Expects a client with .get(key) and .set(key, value, expire=ttl_seconds).
    """

    def __init__(self, client) -> None:
        self.client = client

    def get(self, key: str) -> Any:
        return self.client.get(key)

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expire = int(ttl) if ttl and ttl > 0 else 0
        try:
            # pymemcache: set(key, value, expire=...)
            self.client.set(key, value, expire=expire)
        except TypeError:
            # python-binary-memcached: set(key, value, time=...)
            self.client.set(key, value, time=expire)

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)
        except Exception:
            pass

    def clear(self) -> None:
        try:
            self.client.flush_all()
        except Exception:
            pass
