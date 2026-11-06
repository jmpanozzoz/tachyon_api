"""WebSocket route registration with DI and typed path parameter injection."""

import inspect
from typing import Any, Callable, List, Tuple

from starlette.responses import JSONResponse
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket

from ..utils import TypeConverter, TypeUtils
from ..processing.dependencies._sig_cache import get_signature, prepare_dependency, is_async_callable
from starlette.concurrency import run_in_threadpool

# Param kind constants (parallel to HTTP compiler)
_WS_WEBSOCKET   = 0
_WS_PATH        = 1
_WS_DEP_CLASS   = 2
_WS_DEP_CALLABLE = 3


class WebSocketManager:
    __slots__ = ("_router", "_dependency_resolver")

    def __init__(self, router, dependency_resolver=None) -> None:
        self._router = router
        self._dependency_resolver = dependency_resolver

    def websocket_decorator(self, path: str):
        def decorator(func: Callable):
            self.add_websocket_route(path, func)
            return func
        return decorator

    def add_websocket_route(self, path: str, endpoint_func: Callable, dependencies=()):
        # Pre-compute all param descriptors once at registration time — zero
        # inspect overhead on the hot path.
        from ..di import Depends, _registry
        from ..params import Query, Header, Body, Cookie, Form, File

        dependencies = tuple(dep.dependency if isinstance(dep, Depends) else dep for dep in dependencies)
        for dependency in dependencies:
            if dependency is None or not callable(dependency):
                raise TypeError("WebSocket dependencies must be callables or Depends(callable)")
            prepare_dependency(dependency)
        sig = get_signature(endpoint_func)
        if any(p.kind == inspect.Parameter.POSITIONAL_ONLY for p in sig.parameters.values()):
            raise TypeError("WebSocket endpoints do not support positional-only parameters")
        # List of (kind, param_name, meta) — meta meaning depends on kind:
        #   _WS_PATH       → base Python type for conversion
        #   _WS_DEP_CLASS  → class to resolve via DI registry
        #   _WS_DEP_CALLABLE → callable to invoke via DependencyResolver
        _params: List[Tuple[int, str, Any]] = []

        for p in sig.parameters.values():
            if isinstance(p.default, (Query, Header, Body, Cookie, Form, File)):
                raise TypeError(
                    f"{type(p.default).__name__} marker is not supported for WebSocket parameter '{p.name}'; "
                    "read values from WebSocket or use Header/Query in a Depends factory"
                )
            ann = p.annotation if p.annotation is not inspect.Parameter.empty else str
            if p.name == "websocket" or ann is WebSocket:
                _params.append((_WS_WEBSOCKET, p.name, None))
                continue

            if isinstance(p.default, Depends):
                if p.default.dependency is not None:
                    prepare_dependency(p.default.dependency)
                    _params.append((_WS_DEP_CALLABLE, p.name, p.default.dependency))
                else:
                    prepare_dependency(ann)
                    _params.append((_WS_DEP_CLASS, p.name, ann))
                continue

            if p.default is inspect.Parameter.empty and ann in _registry:
                prepare_dependency(ann)
                _params.append((_WS_DEP_CLASS, p.name, ann))
                continue

            if p.name not in {part.split(":", 1)[0] for part in path.replace("}", "{").split("{")[1::2]}:
                if p.default is inspect.Parameter.empty:
                    raise TypeError(f"Cannot bind WebSocket parameter '{p.name}'")
                continue
            # Path parameter: unwrap Optional[T] to get base type for conversion
            base_type, _ = TypeUtils.unwrap_optional(ann)
            _params.append((_WS_PATH, p.name, base_type))

        if self._dependency_resolver is None and (dependencies or any(kind in (_WS_DEP_CLASS, _WS_DEP_CALLABLE) for kind, _, _ in _params)):
            raise TypeError("WebSocket dependencies require an explicitly bound dependency resolver")

        async def websocket_handler(websocket: WebSocket):
            path_params = websocket.path_params

            # Bind the resolver explicitly rather than depending on scope mutation.
            dep_resolver = self._dependency_resolver

            kwargs = {}
            dep_cache: dict = {}
            for dependency in dependencies:
                await dep_resolver.resolve_callable_dependency(dependency, dep_cache, websocket)

            for kind, name, meta in _params:
                if kind == _WS_WEBSOCKET:
                    kwargs[name] = websocket

                elif kind == _WS_PATH:
                    raw = path_params.get(name)
                    if raw is None:
                        continue
                    if meta is str:
                        kwargs[name] = raw
                    else:
                        converted = TypeConverter.convert_value_bare(
                            raw, meta, name, is_path_param=True
                        )
                        if isinstance(converted, JSONResponse):
                            # Type mismatch — close with policy violation code
                            await websocket.close(code=1008)
                            return
                        kwargs[name] = converted

                elif kind == _WS_DEP_CLASS:
                    if dep_resolver is not None:
                        kwargs[name] = await dep_resolver.resolve_class_dependency(meta, dep_cache, websocket)

                elif kind == _WS_DEP_CALLABLE:
                    if dep_resolver is not None:
                        kwargs[name] = await dep_resolver.resolve_callable_dependency(
                            meta, dep_cache, websocket  # type: ignore[arg-type]
                        )

            if is_async_callable(endpoint_func):
                result = endpoint_func(**kwargs)
            else:
                result = await run_in_threadpool(endpoint_func, **kwargs)
            if inspect.isawaitable(result):
                await result

        route = WebSocketRoute(path, endpoint=websocket_handler)
        self._router.routes.append(route)
