"""WebSocket route registration with DI and typed path parameter injection."""

import inspect
from typing import Any, Callable, List, Tuple

from starlette.responses import JSONResponse
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket

from ..utils import TypeConverter, TypeUtils

# Param kind constants (parallel to HTTP compiler)
_WS_WEBSOCKET   = 0
_WS_PATH        = 1
_WS_DEP_CLASS   = 2
_WS_DEP_CALLABLE = 3


class WebSocketManager:
    def __init__(self, router):
        self._router = router

    def websocket_decorator(self, path: str):
        def decorator(func: Callable):
            self.add_websocket_route(path, func)
            return func
        return decorator

    def add_websocket_route(self, path: str, endpoint_func: Callable):
        # Pre-compute all param descriptors once at registration time — zero
        # inspect overhead on the hot path.
        from ..di import Depends, _registry

        sig = inspect.signature(endpoint_func)
        # List of (kind, param_name, meta) — meta meaning depends on kind:
        #   _WS_PATH       → base Python type for conversion
        #   _WS_DEP_CLASS  → class to resolve via DI registry
        #   _WS_DEP_CALLABLE → callable to invoke via DependencyResolver
        _params: List[Tuple[int, str, Any]] = []

        for p in sig.parameters.values():
            ann = p.annotation if p.annotation is not inspect.Parameter.empty else str
            if p.name == "websocket" or ann is WebSocket:
                _params.append((_WS_WEBSOCKET, p.name, None))
                continue

            if isinstance(p.default, Depends):
                if p.default.dependency is not None:
                    _params.append((_WS_DEP_CALLABLE, p.name, p.default.dependency))
                else:
                    _params.append((_WS_DEP_CLASS, p.name, ann))
                continue

            if p.default is inspect.Parameter.empty and ann in _registry:
                _params.append((_WS_DEP_CLASS, p.name, ann))
                continue

            # Path parameter: unwrap Optional[T] to get base type for conversion
            base_type, _ = TypeUtils.unwrap_optional(ann)
            _params.append((_WS_PATH, p.name, base_type))

        async def websocket_handler(websocket: WebSocket):
            path_params = websocket.path_params

            # Access DI resolver from the app bound to the ASGI scope
            app_instance = websocket.scope.get("app")
            dep_resolver = getattr(app_instance, "_dependency_resolver", None)

            kwargs = {}
            dep_cache: dict = {}

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
                        kwargs[name] = dep_resolver.resolve_dependency(meta)

                elif kind == _WS_DEP_CALLABLE:
                    if dep_resolver is not None:
                        kwargs[name] = await dep_resolver.resolve_callable_dependency(
                            meta, dep_cache, websocket  # type: ignore[arg-type]
                        )

            await endpoint_func(**kwargs)

        route = WebSocketRoute(path, endpoint=websocket_handler)
        self._router.routes.append(route)
