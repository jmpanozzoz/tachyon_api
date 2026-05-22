"""Dependency injection: Depends marker, @injectable registry, and scope management."""

from typing import Dict, Optional, Set, Type, TypeVar, Callable, Any

_registry: Set[Type] = set()
_scopes: Dict[Type, str] = {}  # class → "singleton" | "request" | "transient"

T = TypeVar("T")

SCOPE_SINGLETON  = "singleton"
SCOPE_REQUEST    = "request"
SCOPE_TRANSIENT  = "transient"


class Depends:
    """Marker for explicit dependency injection.

    ``Depends()`` resolves by type annotation (class-based DI).
    ``Depends(callable)`` calls the factory and injects the result.
    """

    def __init__(self, dependency: Optional[Callable[..., Any]] = None):
        self.dependency = dependency


def injectable(_cls: Optional[Type[T]] = None, *, scope: str = SCOPE_SINGLETON) -> Any:
    """Register a class for automatic dependency resolution.

    Supports three scopes:

    - ``"singleton"`` *(default)* — one instance per application lifetime,
      cached in ``app._instances_cache``.
    - ``"request"`` — one instance per HTTP request, cached in the
      per-request ``dependency_cache`` dict.
    - ``"transient"`` — a fresh instance on every injection.

    Usage::

        @injectable                        # singleton (default)
        class DB: ...

        @injectable(scope="request")       # new instance per request
        class RequestContext: ...

        @injectable(scope="transient")     # new instance every time
        class UnitOfWork: ...
    """
    def decorator(cls: Type[T]) -> Type[T]:
        _registry.add(cls)
        _scopes[cls] = scope
        return cls

    if _cls is not None:
        # Called as bare @injectable (no parentheses)
        return decorator(_cls)
    # Called as @injectable(scope=...) — return the decorator
    return decorator
