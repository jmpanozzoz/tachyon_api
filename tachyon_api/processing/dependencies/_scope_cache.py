# HOT PATH — class-dep cache indexed by scope (singleton / request / transient).
#
# Singletons live in `app._instances_cache` (app-wide).
# Request-scoped instances live in the per-request `dependency_cache` dict.
# Transient instances are never cached.

from typing import Any, Dict, Optional, Type

from ...di import SCOPE_REQUEST, SCOPE_SINGLETON, _scopes


class ScopeCache:
    """Looks up and stores class instances according to their declared scope."""

    __slots__ = ("_app",)

    def __init__(self, app) -> None:
        self._app = app

    @staticmethod
    def get_scope(cls: Type) -> str:
        return _scopes.get(cls, SCOPE_SINGLETON)

    def lookup(
        self, cls: Type, scope: str, request_cache: Optional[Dict]
    ) -> Any:
        if scope == SCOPE_SINGLETON:
            return self._app.get_instance(cls)
        if scope == SCOPE_REQUEST and request_cache is not None:
            return request_cache.get(cls)
        # SCOPE_TRANSIENT — never cached
        return None

    def store(
        self,
        cls: Type,
        instance: Any,
        scope: str,
        request_cache: Optional[Dict],
    ) -> None:
        if scope == SCOPE_SINGLETON:
            self._app.register_instance(cls, instance)
        elif scope == SCOPE_REQUEST and request_cache is not None:
            request_cache[cls] = instance
        # SCOPE_TRANSIENT — no-op
