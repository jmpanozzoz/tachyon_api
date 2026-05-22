# HOT PATH — orchestrator that composes the dependency-resolution pipeline.
#
# Public surface (unchanged from v1.2.0):
#   resolve_dependency(cls, request_cache=None) -> instance
#   resolve_callable_dependency(dependency, cache, request) -> awaited result
#
# Pipeline (in order, per call):
#   1. OverrideLookup       → check dependency_overrides registry
#   2. ScopeCache.lookup    → scope-aware cache hit
#   3. _registry fallback   → non-injectable plain class
#   4. CircularDetector     → cycle check before building
#   5. ClassFactory.build / CallableFactory.invoke
#   6. ScopeCache.store     → persist according to scope

import asyncio
from typing import Any, Callable, Dict, Optional, Type

from ...di import _registry
from ._callable_factory import CallableFactory
from ._circular_detector import CircularDetector
from ._class_factory import ClassFactory
from ._override_lookup import _SENTINEL, OverrideLookup
from ._scope_cache import ScopeCache


class DependencyResolver:
    """Orchestrates class-based and callable-based dependency resolution."""

    __slots__ = (
        "app",
        "_overrides",
        "_scope_cache",
        "_circular",
        "_class_factory",
        "_callable_factory",
        # kept for backward compatibility with code that introspected the resolver
        "_resolving",
    )

    def __init__(self, app_instance: Any) -> None:
        self.app = app_instance
        self._overrides = OverrideLookup(app_instance)
        self._scope_cache = ScopeCache(app_instance)
        self._circular = CircularDetector()
        self._class_factory = ClassFactory(self.resolve_dependency)
        self._callable_factory = CallableFactory(
            self.resolve_dependency, self.resolve_callable_dependency
        )
        # legacy attribute — was a set used by the old monolithic resolver
        self._resolving = self._circular._resolving

    def resolve_dependency(
        self, cls: Type, request_cache: Optional[Dict] = None
    ) -> Any:
        override = self._overrides.lookup(cls)
        if override is not _SENTINEL:
            return override

        scope = self._scope_cache.get_scope(cls)
        cached = self._scope_cache.lookup(cls, scope, request_cache)
        if cached is not None:
            return cached

        if cls not in _registry:
            try:
                return cls()
            except TypeError:
                raise TypeError(
                    f"Cannot resolve dependency '{cls.__name__}'. "
                    f"Did you forget to mark it with @injectable?"
                )

        self._circular.check_and_enter(cls)
        try:
            instance = self._class_factory.build(cls, request_cache)
        finally:
            self._circular.exit(cls)

        self._scope_cache.store(cls, instance, scope, request_cache)
        return instance

    async def resolve_callable_dependency(
        self,
        dependency: Callable,
        cache: Optional[Dict],
        request: Any,
    ) -> Any:
        override = self._overrides.lookup(dependency)
        if override is not _SENTINEL:
            if asyncio.iscoroutine(override):
                return await override
            return override

        if cache is not None and dependency in cache:
            return cache[dependency]

        result = await self._callable_factory.invoke(dependency, cache, request)

        if cache is not None:
            cache[dependency] = result
        return result
