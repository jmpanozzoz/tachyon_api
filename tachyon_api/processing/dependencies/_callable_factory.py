# HOT PATH — invokes a `Depends(callable)` factory, resolving its own deps
# recursively, and awaits the result if it's a coroutine.
#
# Note: `asyncio.iscoroutinefunction(dependency)` is unreliable for objects
# with an async `__call__`, so we always check the *result* for being a
# coroutine.

import asyncio
from typing import Any, Callable, Dict, Optional

from starlette.requests import Request

from ...di import Depends
from ..scope import TachyonScope
from ._sig_cache import get_signature


class CallableFactory:
    """Invokes a callable dependency async-aware, recursively resolving its sub-deps."""

    __slots__ = ("_resolve_dep", "_resolve_callable")

    def __init__(
        self,
        resolve_dep: Callable[..., Any],
        resolve_callable: Callable[..., Any],
    ) -> None:
        self._resolve_dep = resolve_dep
        self._resolve_callable = resolve_callable

    async def invoke(
        self, dependency: Callable, cache: Optional[Dict], request: Any
    ) -> Any:
        sig = get_signature(dependency)
        nested_kwargs: Dict[str, Any] = {}

        for param in sig.parameters.values():
            if param.annotation is Request:
                nested_kwargs[param.name] = (
                    request.as_request() if isinstance(request, TachyonScope) else request
                )
            elif isinstance(param.default, Depends):
                if param.default.dependency is not None:
                    nested_kwargs[param.name] = await self._resolve_callable(
                        param.default.dependency, cache, request
                    )
                else:
                    nested_kwargs[param.name] = self._resolve_dep(
                        param.annotation, cache
                    )

        result = dependency(**nested_kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        return result
