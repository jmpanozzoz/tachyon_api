# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled dependency-resolution orchestrator.

Sibling of `_resolver.py`. cdef class wiring the 6 collaborators (override
lookup, scope cache, sig cache, circular detector, class factory, callable
factory) into the resolve_dependency / resolve_callable_dependency pipeline.

Public surface (unchanged from v1.2.0):
  - resolve_dependency(cls, request_cache=None) -> instance
  - resolve_callable_dependency(dependency, cache, request) -> awaited result
"""

import asyncio

from ...di import _registry
from ._callable_factory import CallableFactory
from ._circular_detector import CircularDetector
from ._class_factory import ClassFactory
from ._override_lookup import _SENTINEL, OverrideLookup
from ._scope_cache import ScopeCache


cdef class DependencyResolver:
    """Orchestrates class-based and callable-based dependency resolution."""

    cdef public object app
    cdef object _overrides
    cdef object _scope_cache
    cdef object _circular
    cdef object _class_factory
    cdef object _callable_factory
    # legacy attribute — was a set used by the old monolithic resolver; some
    # external code (and at least one test) introspected it
    cdef public set _resolving

    def __init__(self, app_instance):
        self.app = app_instance
        self._overrides = OverrideLookup(app_instance)
        self._scope_cache = ScopeCache(app_instance)
        self._circular = CircularDetector()
        self._class_factory = ClassFactory(self.resolve_dependency)
        self._callable_factory = CallableFactory(
            self.resolve_dependency, self.resolve_callable_dependency
        )
        self._resolving = self._circular._resolving

    def resolve_dependency(self, cls, request_cache=None):
        override = self._overrides.lookup(cls)
        if override is not _SENTINEL:
            return override

        cdef str scope = self._scope_cache.get_scope(cls)
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

    async def resolve_callable_dependency(self, dependency, cache, request):
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
