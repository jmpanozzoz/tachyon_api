"""
tachyon-engine adapter implementation.

Wraps tachyon-engine objects (Rust-powered ASGI) to implement the adapter interfaces.
Provides 4-7x performance improvement over Starlette.
"""

from typing import Any, Callable, Dict, List, Optional

try:
    from tachyon_engine import (
        TachyonEngine,
        Request as EngineRequest,
        Response as EngineResponse,
        JSONResponse as EngineJSONResponse,
        HTMLResponse as EngineHTMLResponse,
        Route as EngineRoute,
        WebSocketRoute as EngineWebSocketRoute,
        WebSocket as EngineWebSocket,
    )
    TACHYON_ENGINE_AVAILABLE = True
except ImportError:
    TACHYON_ENGINE_AVAILABLE = False
    TachyonEngine = None
    EngineRequest = None
    EngineResponse = None
    EngineJSONResponse = None
    EngineHTMLResponse = None
    EngineRoute = None
    EngineWebSocketRoute = None
    EngineWebSocket = None

from .base import (
    AsgiApplicationAdapter,
    RequestAdapter,
    ResponseAdapter,
    RouteAdapter,
    WebSocketAdapter,
    MiddlewareAdapter,
)


class TachyonEngineApplicationAdapter(AsgiApplicationAdapter):
    """Adapter for tachyon-engine TachyonEngine."""
    
    def __init__(self, lifespan: Optional[Callable] = None, debug: bool = False):
        """Initialize tachyon-engine application."""
        if not TACHYON_ENGINE_AVAILABLE:
            raise ImportError(
                "tachyon-engine is not installed. "
                "Install it with: pip install tachyon-api[engine]"
            )
        
        self._app = TachyonEngine(debug=debug, lifespan=lifespan)
        self._routes = []
    
    def add_route(
        self,
        path: str,
        endpoint: Callable,
        methods: List[str],
        name: Optional[str] = None
    ) -> None:
        """Add HTTP route."""
        route = EngineRoute(path, endpoint, methods=methods, name=name)
        self._app.add_route(route)
        self._routes.append(route)
    
    def add_websocket_route(
        self,
        path: str,
        endpoint: Callable,
        name: Optional[str] = None
    ) -> None:
        """Add WebSocket route."""
        route = EngineWebSocketRoute(path, endpoint, name=name)
        self._app.add_websocket_route(route)
        self._routes.append(route)
    
    def add_middleware(self, middleware_class: type, **options) -> None:
        """
        Add middleware to stack.
        
        Note: tachyon-engine middleware support is being implemented.
        For now, we store middleware but may not apply it.
        """
        # TODO: Implement middleware stacking in tachyon-engine
        # For now, middleware will be handled at a higher level
        pass
    
    async def __call__(self, scope: Dict, receive: Callable, send: Callable):
        """ASGI callable."""
        await self._app(scope, receive, send)
    
    def get_routes(self) -> List[Any]:
        """Get registered routes."""
        return self._routes
    
    def get_state(self) -> Any:
        """Get application state."""
        # tachyon-engine uses app.state attribute
        return self._app.state if hasattr(self._app, 'state') else {}
    
    def get_native(self) -> Any:
        """Get native tachyon-engine app."""
        return self._app


class TachyonEngineRequestAdapter(RequestAdapter):
    """Adapter for tachyon-engine Request."""
    
    def __init__(self, native_request: Any):
        """Initialize request adapter."""
        if not TACHYON_ENGINE_AVAILABLE:
            raise ImportError("tachyon-engine is not installed")
        
        self._request = native_request
    
    @property
    def method(self) -> str:
        """HTTP method."""
        return self._request.method
    
    @property
    def url(self) -> str:
        """Full URL."""
        return self._request.url
    
    @property
    def path(self) -> str:
        """URL path."""
        return self._request.path
    
    @property
    def headers(self) -> Dict[str, str]:
        """HTTP headers."""
        # tachyon-engine Request.headers returns a Headers object
        # which should behave like a dict
        return dict(self._request.headers) if self._request.headers else {}
    
    @property
    def query_params(self) -> Dict[str, str]:
        """Query parameters."""
        # tachyon-engine Request.query_params returns a QueryParams object
        return dict(self._request.query_params) if self._request.query_params else {}
    
    @property
    def path_params(self) -> Dict[str, str]:
        """Path parameters."""
        return dict(self._request.path_params) if self._request.path_params else {}
    
    @property
    def cookies(self) -> Dict[str, str]:
        """Cookies."""
        return dict(self._request.cookies) if self._request.cookies else {}
    
    @property
    def state(self) -> Any:
        """Request state."""
        return self._request.state if hasattr(self._request, 'state') else {}
    
    async def json(self) -> Any:
        """Parse JSON body."""
        # tachyon-engine Request.json() might be sync or async
        result = self._request.json()
        # If it's a coroutine, await it
        if hasattr(result, '__await__'):
            return await result
        return result
    
    async def body(self) -> bytes:
        """Get raw body."""
        # tachyon-engine Request.body() might be sync or async
        result = self._request.body()
        if hasattr(result, '__await__'):
            return await result
        return result
    
    async def form(self) -> Dict[str, Any]:
        """Parse form data."""
        # tachyon-engine Request.form() might be sync or async
        result = self._request.form()
        if hasattr(result, '__await__'):
            return await result
        return result
    
    def get_native(self) -> Any:
        """Get native tachyon-engine request."""
        return self._request


class TachyonEngineResponseAdapter(ResponseAdapter):
    """Adapter for tachyon-engine Response."""
    
    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: Optional[str] = None
    ):
        """Initialize response adapter."""
        if not TACHYON_ENGINE_AVAILABLE:
            raise ImportError("tachyon-engine is not installed")
        
        # Choose appropriate response type
        if isinstance(content, dict):
            # Use JSONResponse for dict content
            self._response = EngineJSONResponse(
                content,
                status_code=status_code,
                headers=headers
            )
        elif media_type == "text/html" or isinstance(content, str) and content.strip().startswith('<'):
            # Use HTMLResponse for HTML content
            self._response = EngineHTMLResponse(
                content,
                status_code=status_code,
                headers=headers
            )
        else:
            # Use regular Response
            self._response = EngineResponse(
                content,
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
            key,
            value,
            max_age=max_age,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite
        )
    
    def get_native(self) -> Any:
        """Get native tachyon-engine response."""
        return self._response


class TachyonEngineRouteAdapter(RouteAdapter):
    """Adapter for tachyon-engine Route."""
    
    def __init__(
        self,
        path: str,
        endpoint: Callable,
        methods: List[str],
        name: Optional[str] = None
    ):
        """Initialize route adapter."""
        if not TACHYON_ENGINE_AVAILABLE:
            raise ImportError("tachyon-engine is not installed")
        
        self._route = EngineRoute(path, endpoint, methods=methods, name=name)
    
    def get_native(self) -> Any:
        """Get native tachyon-engine route."""
        return self._route


class TachyonEngineWebSocketAdapter(WebSocketAdapter):
    """Adapter for tachyon-engine WebSocket."""
    
    def __init__(self, native_websocket: Any):
        """Initialize WebSocket adapter."""
        if not TACHYON_ENGINE_AVAILABLE:
            raise ImportError("tachyon-engine is not installed")
        
        self._websocket = native_websocket
    
    async def accept(self) -> None:
        """Accept connection."""
        result = self._websocket.accept()
        if hasattr(result, '__await__'):
            await result
    
    async def send_text(self, data: str) -> None:
        """Send text message."""
        result = self._websocket.send_text(data)
        if hasattr(result, '__await__'):
            await result
    
    async def send_json(self, data: Any) -> None:
        """Send JSON message."""
        result = self._websocket.send_json(data)
        if hasattr(result, '__await__'):
            await result
    
    async def send_bytes(self, data: bytes) -> None:
        """Send binary message."""
        result = self._websocket.send_bytes(data)
        if hasattr(result, '__await__'):
            await result
    
    async def receive_text(self) -> str:
        """Receive text message."""
        result = self._websocket.receive_text()
        if hasattr(result, '__await__'):
            return await result
        return result
    
    async def receive_json(self) -> Any:
        """Receive JSON message."""
        result = self._websocket.receive_json()
        if hasattr(result, '__await__'):
            return await result
        return result
    
    async def receive_bytes(self) -> bytes:
        """Receive binary message."""
        result = self._websocket.receive_bytes()
        if hasattr(result, '__await__'):
            return await result
        return result
    
    async def close(self, code: int = 1000) -> None:
        """Close connection."""
        result = self._websocket.close(code)
        if hasattr(result, '__await__'):
            await result
    
    @property
    def path_params(self) -> Dict[str, str]:
        """Path parameters."""
        return dict(self._websocket.path_params) if self._websocket.path_params else {}
    
    @property
    def query_params(self) -> Dict[str, str]:
        """Query parameters."""
        return dict(self._websocket.query_params) if self._websocket.query_params else {}
    
    def get_native(self) -> Any:
        """Get native tachyon-engine WebSocket."""
        return self._websocket


class TachyonEngineMiddlewareAdapter(MiddlewareAdapter):
    """Adapter for tachyon-engine Middleware."""
    
    def __init__(self, middleware_class: type, **options):
        """Initialize middleware adapter."""
        if not TACHYON_ENGINE_AVAILABLE:
            raise ImportError("tachyon-engine is not installed")
        
        # TODO: tachyon-engine middleware implementation
        self._middleware_class = middleware_class
        self._options = options
    
    def get_native(self) -> Any:
        """Get native middleware object."""
        # For now, return the class and options as a tuple
        return (self._middleware_class, self._options)
