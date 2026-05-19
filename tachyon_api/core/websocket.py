"""WebSocket route registration with path parameter injection."""

import inspect
from typing import Callable

from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket


class WebSocketManager:
    def __init__(self, router):
        self._router = router

    def websocket_decorator(self, path: str):
        def decorator(func: Callable):
            self.add_websocket_route(path, func)
            return func

        return decorator

    def add_websocket_route(self, path: str, endpoint_func: Callable):
        async def websocket_handler(websocket: WebSocket):
            path_params = websocket.path_params
            kwargs = {"websocket": websocket}
            sig = inspect.signature(endpoint_func)
            for param in sig.parameters.values():
                if param.name != "websocket" and param.name in path_params:
                    kwargs[param.name] = path_params[param.name]
            await endpoint_func(**kwargs)

        route = WebSocketRoute(path, endpoint=websocket_handler)
        self._router.routes.append(route)

