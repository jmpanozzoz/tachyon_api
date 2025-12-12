"""
WebSocket handling for Tachyon applications.

Handles:
- WebSocket route registration
- Path parameter injection
- WebSocket handler wrapping
"""

import inspect
from typing import Callable

from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket


class WebSocketManager:
    """
    Manages WebSocket routes and handlers.
    
    This class encapsulates the logic for:
    - Registering WebSocket endpoints via decorator
    - Wrapping user handlers with parameter injection
    - Path parameter extraction and injection
    """
    
    def __init__(self, router):
        """
        Initialize WebSocket manager.
        
        Args:
            router: The Starlette router instance
        """
        self._router = router
    
    def websocket_decorator(self, path: str):
        """
        Create a decorator to register a WebSocket endpoint.

        Args:
            path: URL path pattern for the WebSocket endpoint

        Returns:
            A decorator that registers the WebSocket handler

        Example:
            @app.websocket("/ws")
            async def websocket_endpoint(websocket):
                await websocket.accept()
                data = await websocket.receive_text()
                await websocket.send_text(f"Echo: {data}")
                await websocket.close()

            @app.websocket("/ws/{room_id}")
            async def room_endpoint(websocket, room_id: str):
                await websocket.accept()
                await websocket.send_text(f"Welcome to {room_id}")
                await websocket.close()
        """

        def decorator(func: Callable):
            self.add_websocket_route(path, func)
            return func

        return decorator
    
    def add_websocket_route(self, path: str, endpoint_func: Callable):
        """
        Register a WebSocket route with the application.

        Args:
            path: URL path pattern (supports path parameters)
            endpoint_func: The async WebSocket handler function
        """

        async def websocket_handler(websocket: WebSocket):
            # Extract path parameters
            path_params = websocket.path_params

            # Build kwargs for the handler
            kwargs = {"websocket": websocket}

            # Inject path parameters if the handler accepts them
            sig = inspect.signature(endpoint_func)
            for param in sig.parameters.values():
                if param.name != "websocket" and param.name in path_params:
                    kwargs[param.name] = path_params[param.name]

            await endpoint_func(**kwargs)

        route = WebSocketRoute(path, endpoint=websocket_handler)
        self._router.routes.append(route)

