"""Dependency injection resolution (type-based and callable-based)."""

import asyncio
import inspect
from typing import Any, Callable, Dict, Type

from starlette.requests import Request

from ..di import Depends, _registry


class DependencyResolver:
    def __init__(self, app_instance):
        self.app = app_instance
        self._resolving: set = set()

    def resolve_dependency(self, cls: Type) -> Any:
        if cls in self.app.dependency_overrides:
            override = self.app.dependency_overrides[cls]
            if callable(override) and not isinstance(override, type):
                return override()
            elif isinstance(override, type):
                return override()
            return override

        if cls in self.app._instances_cache:
            return self.app._instances_cache[cls]

        if cls not in _registry:
            try:
                return cls()
            except TypeError:
                raise TypeError(
                    f"Cannot resolve dependency '{cls.__name__}'. "
                    f"Did you forget to mark it with @injectable?"
                )

        if cls in self._resolving:
            raise TypeError(
                f"Circular dependency detected while resolving '{cls.__name__}'"
            )

        sig = inspect.signature(cls)
        dependencies = {}
        self._resolving.add(cls)
        try:
            for param in sig.parameters.values():
                if param.name != "self":
                    if param.annotation is inspect.Parameter.empty:
                        raise TypeError(
                            f"Parameter '{param.name}' in '{cls.__name__}' has no type annotation; "
                            f"cannot resolve dependency."
                        )
                    dependencies[param.name] = self.resolve_dependency(param.annotation)
        finally:
            self._resolving.discard(cls)

        instance = cls(**dependencies)
        self.app._instances_cache[cls] = instance
        return instance

    async def resolve_callable_dependency(
        self, dependency: Callable, cache: Dict, request: Request
    ) -> Any:
        if dependency in self.app.dependency_overrides:
            override = self.app.dependency_overrides[dependency]
            if callable(override):
                result = override()
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            return override

        if dependency in cache:
            return cache[dependency]

        sig = inspect.signature(dependency)
        nested_kwargs = {}
        for param in sig.parameters.values():
            if param.annotation is Request:
                nested_kwargs[param.name] = request
            elif isinstance(param.default, Depends):
                if param.default.dependency is not None:
                    nested_kwargs[param.name] = await self.resolve_callable_dependency(
                        param.default.dependency, cache, request
                    )
                else:
                    nested_kwargs[param.name] = self.resolve_dependency(param.annotation)

        # asyncio.iscoroutinefunction doesn't detect async __call__ methods,
        # so we call and check if the result is a coroutine
        result = dependency(**nested_kwargs)
        if asyncio.iscoroutine(result):
            result = await result

        cache[dependency] = result
        return result

