"""
Dependency resolution for Tachyon applications.

Handles:
- Type-based dependency injection (@injectable)
- Callable dependency injection (Depends(callable))
- Nested dependencies
- Dependency caching (singleton and per-request)
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, Type

from starlette.requests import Request

from ..di import Depends, _registry


class DependencyResolver:
    """
    Resolves dependencies for endpoint functions.
    
    This class encapsulates the logic for:
    - Resolving @injectable classes
    - Resolving Depends(callable) functions
    - Handling nested dependencies
    - Caching instances
    - Supporting dependency overrides for testing
    """
    
    def __init__(self, app_instance):
        """
        Initialize dependency resolver.
        
        Args:
            app_instance: The Tachyon app instance
        """
        self.app = app_instance
    
    def resolve_dependency(self, cls: Type) -> Any:
        """
        Resolve a dependency and its sub-dependencies recursively.

        This method implements dependency injection with singleton pattern,
        automatically resolving constructor dependencies and caching instances.

        Args:
            cls: The class type to resolve and instantiate

        Returns:
            An instance of the requested class with all dependencies resolved

        Raises:
            TypeError: If the class cannot be instantiated or is not marked as injectable

        Note:
            - Uses singleton pattern - instances are cached and reused
            - Supports both @injectable decorated classes and simple classes
            - Recursively resolves constructor dependencies
            - Checks dependency_overrides for test mocking
        """
        # Check for dependency override (for testing)
        if cls in self.app.dependency_overrides:
            override = self.app.dependency_overrides[cls]
            # If override is callable, call it to get the instance
            if callable(override) and not isinstance(override, type):
                return override()
            # If it's a class, instantiate it
            elif isinstance(override, type):
                return override()
            # Otherwise return as-is
            return override

        # Return cached instance if available (singleton pattern)
        if cls in self.app._instances_cache:
            return self.app._instances_cache[cls]

        # For non-injectable classes, try to create without arguments
        if cls not in _registry:
            try:
                # Works for classes without __init__ or with no-arg __init__
                return cls()
            except TypeError:
                raise TypeError(
                    f"Cannot resolve dependency '{cls.__name__}'. "
                    f"Did you forget to mark it with @injectable?"
                )

        # For injectable classes, resolve constructor dependencies
        sig = inspect.signature(cls)
        dependencies = {}

        # Recursively resolve each constructor parameter
        for param in sig.parameters.values():
            if param.name != "self":
                dependencies[param.name] = self.resolve_dependency(param.annotation)

        # Create instance with resolved dependencies and cache it
        instance = cls(**dependencies)
        self.app._instances_cache[cls] = instance
        return instance
    
    async def resolve_callable_dependency(
        self, dependency: Callable, cache: Dict, request: Request
    ) -> Any:
        """
        Resolve a callable dependency (function, lambda, or class).

        This method calls the dependency function to get its value, supporting
        both sync and async functions. It also handles nested dependencies
        if the callable has parameters with Depends() or Request annotations.

        Args:
            dependency: The callable to invoke
            cache: Per-request cache to avoid calling the same dependency twice
            request: The current request object for injection

        Returns:
            The result of calling the dependency function

        Note:
            - Results are cached per-request to avoid duplicate calls
            - Supports async callables (coroutines)
            - Supports nested Depends() in callable parameters
            - Automatically injects Request when parameter is annotated with Request
        """
        # Check for dependency override (for testing)
        if dependency in self.app.dependency_overrides:
            override = self.app.dependency_overrides[dependency]
            # If override is callable, call it
            if callable(override):
                result = override()
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            return override

        # Check cache first (same callable = same result per request)
        if dependency in cache:
            return cache[dependency]

        # Check if the dependency has its own dependencies (nested)
        sig = inspect.signature(dependency)
        nested_kwargs = {}

        for param in sig.parameters.values():
            # Inject Request object if parameter is annotated with Request
            if param.annotation is Request:
                nested_kwargs[param.name] = request
            elif isinstance(param.default, Depends):
                if param.default.dependency is not None:
                    # Nested callable dependency
                    nested_kwargs[param.name] = await self.resolve_callable_dependency(
                        param.default.dependency, cache, request
                    )
                else:
                    # Nested type-based dependency
                    nested_kwargs[param.name] = self.resolve_dependency(
                        param.annotation
                    )

        # Call the dependency (sync or async)
        # Note: asyncio.iscoroutinefunction doesn't work for async __call__ methods,
        # so we check if the result is a coroutine
        result = dependency(**nested_kwargs)
        if asyncio.iscoroutine(result):
            result = await result

        # Cache the result for this request
        cache[dependency] = result
        return result
