"""
Starlette adapter implementation.

Wraps Starlette objects to implement the adapter interfaces.
This maintains backward compatibility and serves as the baseline implementation.
"""

from typing import Any, Callable, Dict, List, Optional

from starlette.applications import Starlette
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse, JSONResponse as StarletteJSONResponse
from starlette.routing import Route as StarletteRoute, WebSocketRoute as StarletteWebSocketRoute
from starlette.websockets import WebSocket as StarletteWebSocket
from starlette.middleware import Middleware as StarletteMiddleware

from .base import (
    AsgiApplicationAdapter,
    RequestAdapter,
    ResponseAdapter,
    RouteAdapter,
    WebSocketAdapter,
    MiddlewareAdapter,
)


class StarletteApplicationAdapter(AsgiApplicationAdapter):
    """Adapter for Starlette Application."""
    
    def __init__(self, lifespan: Optional[Callable] = None, debug: bool = False):
        """Initialize Starlette application."""
        self._app = Starlette(debug=debug, lifespan=lifespan)
    
    def add_route(
        self,
        path: str,
        endpoint: Callable,
        methods: List[str],
        name: Optional[str] = None
    ) -> None:
        """Add HTTP route."""
        route = StarletteRoute(path, endpoint=endpoint, methods=methods, name=name)
        self._app.routes.append(route)
    
    def add_websocket_route(
        self,
        path: str,
        endpoint: Callable,
        name: Optional[str] = None
    ) -> None:
        """Add WebSocket route."""
        route = StarletteWebSocketRoute(path, endpoint=endpoint, name=name)
        self._app.routes.append(route)
    
    def add_middleware(self, middleware_class: type, **options) -> None:
        """Add middleware to stack."""
        self._app.user_middleware.insert(0, StarletteMiddleware(middleware_class, **options))
        self._app.middleware_stack = self._app.build_middleware_stack()
    
    async def __call__(self, scope: Dict, receive: Callable, send: Callable):
        """ASGI callable."""
        await self._app(scope, receive, send)
    
    def get_routes(self) -> List[Any]:
        """Get registered routes."""
        return self._app.routes
    
    def get_state(self) -> Any:
        """Get application state."""
        return self._app.state
    
    def get_native(self) -> Starlette:
        """Get native Starlette app."""
        return self._app


class StarletteRequestAdapter(RequestAdapter):
    """Adapter for Starlette Request."""
    
    def __init__(self, native_request: StarletteRequest):
        """Initialize request adapter."""
        self._request = native_request
    
    @property
    def method(self) -> str:
        """HTTP method."""
        return self._request.method
    
    @property
    def url(self) -> str:
        """Full URL."""
        return str(self._request.url)
    
    @property
    def path(self) -> str:
        """URL path."""
        return self._request.url.path
    
    @property
    def headers(self) -> Dict[str, str]:
        """HTTP headers."""
        return dict(self._request.headers)
    
    @property
    def query_params(self) -> Dict[str, str]:
        """Query parameters."""
        return dict(self._request.query_params)
    
    @property
    def path_params(self) -> Dict[str, str]:
        """Path parameters."""
        return dict(self._request.path_params)
    
    @property
    def cookies(self) -> Dict[str, str]:
        """Cookies."""
        return dict(self._request.cookies)
    
    @property
    def state(self) -> Any:
        """Request state."""
        return self._request.state
    
    async def json(self) -> Any:
        """Parse JSON body."""
        return await self._request.json()
    
    async def body(self) -> bytes:
        """Get raw body."""
        return await self._request.body()
    
    async def form(self) -> Dict[str, Any]:
        """Parse form data."""
        return await self._request.form()
    
    def get_native(self) -> StarletteRequest:
        """Get native Starlette request."""
        return self._request


class StarletteResponseAdapter(ResponseAdapter):
    """Adapter for Starlette Response."""
    
    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: Optional[str] = None
    ):
        """Initialize response adapter."""
        if isinstance(content, dict):
            # If content is dict, use JSONResponse
            self._response = StarletteJSONResponse(
                content=content,
                status_code=status_code,
                headers=headers
            )
        else:
            # Otherwise use regular Response
            self._response = StarletteResponse(
                content=content,
                status_code=status_code,
                headers=headers,
                media_type=media_type
            )
    
    def set_cookie(
        self,
        key: str,
        value: str,
        max_age: Optional[int] = None,
        path: Optional[str] = None,
        domain: Optional[str] = None,
        secure: Optional[bool] = None,
        httponly: Optional[bool] = None,
        samesite: Optional[str] = None
    ) -> None:
        """Set cookie."""
        self._response.set_cookie(
            key=key,
            value=value,
            max_age=max_age,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite
        )
    
    def get_native(self) -> StarletteResponse:
        """Get native Starlette response."""
        return self._response


class StarletteRouteAdapter(RouteAdapter):
    """Adapter for Starlette Route."""
    
    def __init__(
        self,
        path: str,
        endpoint: Callable,
        methods: List[str],
        name: Optional[str] = None
    ):
        """Initialize route adapter."""
        self._route = StarletteRoute(path, endpoint=endpoint, methods=methods, name=name)
    
    def get_native(self) -> StarletteRoute:
        """Get native Starlette route."""
        return self._route


class StarletteWebSocketAdapter(WebSocketAdapter):
    """Adapter for Starlette WebSocket."""
    
    def __init__(self, native_websocket: StarletteWebSocket):
        """Initialize WebSocket adapter."""
        self._websocket = native_websocket
    
    async def accept(self) -> None:
        """Accept connection."""
        await self._websocket.accept()
    
    async def send_text(self, data: str) -> None:
        """Send text message."""
        await self._websocket.send_text(data)
    
    async def send_json(self, data: Any) -> None:
        """Send JSON message."""
        await self._websocket.send_json(data)
    
    async def send_bytes(self, data: bytes) -> None:
        """Send binary message."""
        await self._websocket.send_bytes(data)
    
    async def receive_text(self) -> str:
        """Receive text message."""
        return await self._websocket.receive_text()
    
    async def receive_json(self) -> Any:
        """Receive JSON message."""
        return await self._websocket.receive_json()
    
    async def receive_bytes(self) -> bytes:
        """Receive binary message."""
        return await self._websocket.receive_bytes()
    
    async def close(self, code: int = 1000) -> None:
        """Close connection."""
        await self._websocket.close(code=code)
    
    @property
    def path_params(self) -> Dict[str, str]:
        """Path parameters."""
        return dict(self._websocket.path_params)
    
    @property
    def query_params(self) -> Dict[str, str]:
        """Query parameters."""
        return dict(self._websocket.query_params)
    
    def get_native(self) -> StarletteWebSocket:
        """Get native Starlette WebSocket."""
        return self._websocket


class StarletteMiddlewareAdapter(MiddlewareAdapter):
    """Adapter for Starlette Middleware."""
    
    def __init__(self, middleware_class: type, **options):
        """Initialize middleware adapter."""
        self._middleware = StarletteMiddleware(middleware_class, **options)
    
    def get_native(self) -> StarletteMiddleware:
        """Get native Starlette middleware."""
        return self._middleware
