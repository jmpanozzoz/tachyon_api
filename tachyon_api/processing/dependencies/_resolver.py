"""Class and callable resolution with request-local cycle detection and scope caches."""

import asyncio
import inspect
from threading import RLock
from contextvars import ContextVar

from starlette.concurrency import run_in_threadpool
from ._sig_cache import prepare_dependency

from typing import Any, Dict, Optional, Type

from ...di import _registry
from ._callable_factory import CallableFactory
from ._class_factory import ClassFactory
from ._override_lookup import _SENTINEL, OverrideLookup
from ._scope_cache import ScopeCache

_RESOLUTION_STACK = ContextVar("tachyon_dependency_stack", default=())
_SINGLETON_CAPTURE = ContextVar("tachyon_singleton_capture", default=False)


class DependencyResolver:
    """Orchestrates class-based and callable-based dependency resolution."""

    __slots__ = (
        "app",
        "_overrides",
        "_scope_cache",
        "_class_factory",
        "_callable_factory", "_locks", "_sync_locks",
    )

    def __init__(self, app_instance: Any) -> None:
        self.app = app_instance
        self._locks = {}
        self._sync_locks = {}
        self._overrides = OverrideLookup(app_instance)
        self._scope_cache = ScopeCache(app_instance)
        self._class_factory = ClassFactory(self.resolve_dependency)
        self._callable_factory = CallableFactory(self.resolve_callable_dependency)

    def resolve_dependency(
        self, cls: Type, request_cache: Optional[Dict] = None
    ) -> Any:
        if cls in _registry:
            prepare_dependency(cls, overrides=self.app.dependency_overrides, captured=_SINGLETON_CAPTURE.get())
        override = self._overrides.get_override(cls)
        if override is not _SENTINEL:
            if callable(override):
                prepare_dependency(override, captured=_SINGLETON_CAPTURE.get())
                override = self._class_factory.build(override, request_cache)
            if inspect.isawaitable(override):
                if inspect.iscoroutine(override):
                    override.close()
                raise TypeError("Async dependency overrides require asynchronous resolution")
            return override

        scope = self._scope_cache.get_scope(cls)
        if cls not in _registry:
            try:
                return cls()
            except TypeError:
                raise TypeError(
                    f"Cannot resolve dependency '{cls.__name__}'. "
                    f"Did you forget to mark it with @injectable?"
                )
        stack = _RESOLUTION_STACK.get()
        if cls in stack:
            raise TypeError(f"Circular dependency detected while resolving '{cls.__name__}'")
        token = _RESOLUTION_STACK.set(stack + (cls,))
        try:
            if scope == "singleton":
                lock = self._sync_locks.get(cls)
                if lock is None:
                    lock = self._sync_locks.setdefault(cls, RLock())
                with lock:
                    return self._build_sync_class(cls, scope, request_cache)
            return self._build_sync_class(cls, scope, request_cache)
        finally:
            _RESOLUTION_STACK.reset(token)

    def _build_sync_class(self, cls, scope, request_cache):
        cached = self._scope_cache.lookup(cls, scope, request_cache)
        if cached is not None:
            return cached
        capture_token = _SINGLETON_CAPTURE.set(True) if scope == "singleton" else None
        try:
            instance = self._class_factory.build(cls, request_cache)
            if scope == "singleton":
                prepare_dependency(cls, overrides=self.app.dependency_overrides, captured=True)
            self._scope_cache.store(cls, instance, scope, request_cache)
            return instance
        finally:
            if capture_token is not None:
                _SINGLETON_CAPTURE.reset(capture_token)

    async def _invoke_override(self, override, cache=None, request=None):
        if callable(override):
            prepare_dependency(override, captured=_SINGLETON_CAPTURE.get())
            override = await self._callable_factory.invoke(override, cache, request)
        if inspect.isawaitable(override):
            override = await override
        return override

    async def resolve_class_dependency(self, cls, cache=None, request=None):
        if cls in _registry:
            prepare_dependency(cls, overrides=self.app.dependency_overrides, captured=_SINGLETON_CAPTURE.get())
        override = self._overrides.get_override(cls)
        if override is not _SENTINEL:
            if callable(override):
                prepare_dependency(override, captured=_SINGLETON_CAPTURE.get())
            override_key = ("override", cls)
            if cache is not None and override_key in cache:
                previous_override, instance = cache[override_key]
                if previous_override is override:
                    return instance
            instance = await self._invoke_override(override, cache, request)
            if cache is not None:
                cache[override_key] = (override, instance)
            return instance
        scope = self._scope_cache.get_scope(cls)
        cached = self._scope_cache.lookup(cls, scope, cache)
        if cached is not None:
            return cached
        stack = _RESOLUTION_STACK.get()
        if cls in stack:
            raise TypeError(f"Circular dependency detected while resolving '{cls.__name__}'")
        token = _RESOLUTION_STACK.set(stack + (cls,))
        try:
            # Singleton factories may yield while another request resolves the
            # same class. Recheck under the app-local construction lock.
            if scope == "singleton":
                lock = self._locks.setdefault(cls, asyncio.Lock())
                async with lock:
                    cached = self._scope_cache.lookup(cls, scope, cache)
                    if cached is not None:
                        return cached
                    capture_token = _SINGLETON_CAPTURE.set(True)
                    try:
                        instance = await self._build_class(cls, cache, request)
                        prepare_dependency(cls, overrides=self.app.dependency_overrides, captured=True)
                        self._scope_cache.store(cls, instance, scope, cache)
                        return instance
                    finally:
                        _SINGLETON_CAPTURE.reset(capture_token)
            instance = await self._build_class(cls, cache, request)
            self._scope_cache.store(cls, instance, scope, cache)
            return instance
        finally:
            _RESOLUTION_STACK.reset(token)

    async def _build_class(self, cls, cache, request):
        if cls not in _registry:
            return await run_in_threadpool(cls)
        return await self._callable_factory.invoke(cls, cache, request)

    async def resolve_callable_dependency(self, dependency, cache, request):
        # Depends(Class) uses the class scope just like Depends() + annotation.
        # Class resolution performs the same validation before its cache lookup.
        if isinstance(dependency, type) and dependency in _registry:
            return await self.resolve_class_dependency(dependency, cache, request)
        prepare_dependency(dependency, overrides=self.app.dependency_overrides, captured=_SINGLETON_CAPTURE.get())
        if cache is not None and dependency in cache:
            return cache[dependency]
        stack = _RESOLUTION_STACK.get()
        if dependency in stack:
            raise TypeError(f"Circular dependency detected while resolving {dependency!r}")
        token = _RESOLUTION_STACK.set(stack + (dependency,))
        try:
            override = self._overrides.get_override(dependency)
            if override is not _SENTINEL:
                result = await self._invoke_override(override, cache, request)
            else:
                result = await self._callable_factory.invoke(dependency, cache, request)
            if cache is not None:
                cache[dependency] = result
            return result
        finally:
            _RESOLUTION_STACK.reset(token)
