"""
Dependency Injection System for Tachyon API

This module handles the resolution and injection of dependencies for the Tachyon framework.
It provides both explicit and implicit dependency injection capabilities.
"""

from typing import Any, Type, Dict
import inspect

from .injection import _registry


class DependencyResolver:
    """
    Handles dependency resolution and injection for the Tachyon framework.

    This class implements a singleton pattern for dependency caching and supports
    both @injectable decorated classes and simple classes for dependency injection.
    """

    def __init__(self):
        """Initialize the dependency resolver with an empty cache."""
        self._instances_cache: Dict[Type, Any] = {}

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
        """
        # Return cached instance if available (singleton pattern)
        if cls in self._instances_cache:
            return self._instances_cache[cls]

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
        self._instances_cache[cls] = instance
        return instance

    def clear_cache(self):
        """Clear the dependency cache. Useful for testing."""
        self._instances_cache.clear()
