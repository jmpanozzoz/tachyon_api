"""
Tachyon Web Framework - Dependency Injection Module

This module provides a lightweight dependency injection system that supports
both explicit and implicit dependency resolution with singleton pattern.
"""

from typing import Set, Type, TypeVar, Callable, Optional, Any

# Global registry of injectable classes
_registry: Set[Type] = set()

T = TypeVar("T")


class Depends:
    """
    Marker class for explicit dependency injection.

    Use this as a default parameter value to explicitly mark a parameter
    as a dependency that should be resolved and injected automatically.

    Supports two modes:
    1. Type-based: Depends() - resolves the dependency based on type annotation
    2. Callable-based: Depends(callable) - calls the function to get the value

    Example (type-based):
        @app.get("/users")
        def get_users(service: UserService = Depends()):
            return service.list_all()

    Example (callable-based):
        def get_db():
            return DatabaseConnection()

        @app.get("/items")
        def get_items(db = Depends(get_db)):
            return db.query("SELECT * FROM items")

    Example (async callable):
        async def get_current_user():
            return await fetch_user_from_token()

        @app.get("/profile")
        async def profile(user = Depends(get_current_user)):
            return {"name": user.name}
    """

    def __init__(self, dependency: Optional[Callable[..., Any]] = None):
        """
        Initialize a dependency marker.

        Args:
            dependency: Optional callable (function, lambda, class) that will be
                       called to produce the dependency value. If None, the
                       dependency is resolved based on the parameter's type annotation.
        """
        self.dependency = dependency


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
