"""Dependency invocation with prepared binding and worker-thread execution."""

import inspect
import json
from typing import Any, Callable, Dict, Optional

from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from ..scope import TachyonScope
from ._sig_cache import get_bindings, is_async_callable


class CallableFactory:
    __slots__ = ("_resolve_callable", "_header", "_query", "_query_list")

    def __init__(self, resolve_callable: Callable) -> None:
        from .._extractors import HeaderExtractor, QueryExtractor, QueryListExtractor
        self._resolve_callable = resolve_callable
        self._header = HeaderExtractor()
        self._query = QueryExtractor()
        self._query_list = QueryListExtractor()

    async def invoke(self, dependency: Callable, cache: Optional[Dict], request: Any) -> Any:
        args = []
        kwargs = {}
        for name, positional, kind, target in get_bindings(dependency):
            if kind == "request":
                value = request.as_request() if isinstance(request, TachyonScope) else request
            elif kind == "dependency":
                value = await self._resolve_callable(target, cache, request)
            elif kind == "marker":
                from ..compiler import KIND_HEADER
                if request is None:
                    raise TypeError("Dependency request parameters require an HTTP request or WebSocket")
                if target.kind == KIND_HEADER:
                    value, error = self._header.extract(target, request)
                else:
                    extractor = self._query_list if target.is_list else self._query
                    value, error = extractor.extract(target, request.query_params)
                if error is not None:
                    raise HTTPException(error.status_code, detail=json.loads(error.body)["error"])
            else:
                value = target
            if positional:
                args.append(value)
            else:
                kwargs[name] = value
        if is_async_callable(dependency):
            result = dependency(*args, **kwargs)
        else:
            result = await run_in_threadpool(dependency, *args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result
