"""
Tachyon Web Framework - Dependency Injection Module

This module provides a lightweight dependency injection system that supports
both explicit and implicit dependency resolution with singleton pattern.
"""

from typing import Set, Type, TypeVar

# Global registry of injectable classes
_registry: Set[Type] = set()

T = TypeVar("T")


class Depends:
    """
    Marker class for explicit dependency injection.

    Use this as a default parameter value to explicitly mark a parameter
    as a dependency that should be resolved and injected automatically.

    Example:
        @app.get("/users")
        def get_users(service: UserService = Depends()):
            return service.list_all()
    """

    def __init__(self):
        """Initialize a dependency marker."""
        pass


def injectable(cls: Type[T]) -> Type[T]:
    """
    Decorator to mark a class as injectable for dependency injection.

    Classes marked with this decorator can be automatically resolved and
    injected into endpoint functions and other injectable classes.

    Args:
        cls: The class to mark as injectable

    Returns:
        The same class, now registered for dependency injection

    Example:
        @injectable
        class UserRepository:
            def __init__(self, db: Database):
                self.db = db

        @injectable
        class UserService:
            def __init__(self, repo: UserRepository):
                self.repo = repo
    """
    _registry.add(cls)
    return cls
