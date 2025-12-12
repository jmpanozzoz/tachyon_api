"""
WebSocket handling for Tachyon applications.

Handles:
- WebSocket route registration
- Path parameter injection
- WebSocket handler wrapping
"""

import inspect
from typing import Callable, Any


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

        async def websocket_handler(websocket: Any):
            """
            Generic WebSocket handler that works with both Starlette and tachyon-engine.
            
            Args:
                websocket: WebSocket object (Starlette or tachyon-engine)
            """
            # Extract path parameters (both Starlette and tachyon-engine have this)
            path_params = websocket.path_params

            # Build kwargs for the handler
            kwargs = {"websocket": websocket}

            # Inject path parameters if the handler accepts them
            sig = inspect.signature(endpoint_func)
            for param in sig.parameters.values():
                if param.name != "websocket" and param.name in path_params:
                    kwargs[param.name] = path_params[param.name]

            # Call the user's handler
            await endpoint_func(**kwargs)

        # Register the WebSocket route with the native router
        # Detect which engine we're using by checking the class name
        router_class_name = type(self._router).__name__
        
        if router_class_name == 'TachyonEngine':
            # tachyon-engine style
            try:
                from tachyon_engine import WebSocketRoute as EngineWSRoute
                route = EngineWSRoute(path, websocket_handler)
                self._router.add_websocket_route(route)
            except ImportError:
                # Fallback to Starlette if tachyon-engine not available
                from starlette.routing import WebSocketRoute
                route = WebSocketRoute(path, endpoint=websocket_handler)
                self._router.routes.append(route)
        else:
            # Starlette style (or any other router with .routes list)
            from starlette.routing import WebSocketRoute
            route = WebSocketRoute(path, endpoint=websocket_handler)
            self._router.routes.append(route)



