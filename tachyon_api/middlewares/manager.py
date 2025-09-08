"""
Starlette-Native Middleware Management for Tachyon API

This module provides middleware management that closely follows Starlette's patterns
while maintaining backward compatibility with existing Tachyon functionality.
"""

from typing import Type
from starlette.applications import Starlette

from .core import create_decorated_middleware_class


class StarletteMiddlewareManager:
    """
    Starlette-native middleware manager that follows Starlette's patterns.

    This manager provides a thin wrapper around Starlette's middleware system
    while maintaining compatibility with Tachyon's decorator-based middleware.
    """

    def __init__(self, router: Starlette):
        """
        Initialize the middleware manager.

        Args:
            router: The Starlette application instance to apply middlewares to
        """
        self._router = router

    def add_middleware(self, middleware_class: Type, **options):
        """
        Add a middleware to the Starlette application.

        This method directly uses Starlette's middleware API for maximum compatibility
        with future Starlette/Rust versions.

        Args:
            middleware_class: The middleware class.
            **options: Options to be passed to the middleware constructor.
        """
        # Use Starlette's native middleware API
        self._router.add_middleware(middleware_class, **options)

    def middleware(self, middleware_type: str = "http"):
        """
        Decorator for adding a middleware to the application.
        Similar to route decorators (@app.get, etc.)

        Args:
            middleware_type: Type of middleware ('http' by default)

        Returns:
            A decorator that registers the decorated function as middleware.
        """

        def decorator(middleware_func):
            # Create a middleware class from the decorated function
            DecoratedMiddleware = create_decorated_middleware_class(
                middleware_func, middleware_type
            )
            # Register the middleware using Starlette's native API
            self.add_middleware(DecoratedMiddleware)
            return middleware_func

        return decorator


# Backward compatibility alias
MiddlewareManager = StarletteMiddlewareManager
