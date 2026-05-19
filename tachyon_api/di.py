"""Dependency injection: Depends marker and @injectable registry."""

from typing import Set, Type, TypeVar, Callable, Optional, Any

_registry: Set[Type] = set()

T = TypeVar("T")


class Depends:
    """
    Marker for explicit dependency injection.

    Depends() resolves by type annotation; Depends(callable) calls the factory.
    """

    def __init__(self, dependency: Optional[Callable[..., Any]] = None):
        self.dependency = dependency


def injectable(cls: Type[T]) -> Type[T]:
    """Decorator to register a class for automatic dependency resolution."""
    _registry.add(cls)
    return cls
