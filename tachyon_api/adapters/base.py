"""
Base adapter interfaces for ASGI engines.

Defines abstract interfaces that both Starlette and tachyon-engine adapters must implement.
This allows for a plug-and-play architecture where engines can be swapped transparently.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional


class AsgiApplicationAdapter(ABC):
    """
    Abstract adapter for ASGI application instances.
    
    Wraps the underlying ASGI server (Starlette or tachyon-engine)
    and provides a unified interface for route management, middleware, and request handling.
    """
    
    @abstractmethod
    def __init__(self, lifespan: Optional[Callable] = None, debug: bool = False):
        """
        Initialize the ASGI application.
        
        Args:
            lifespan: Optional lifespan context manager for startup/shutdown events
            debug: Enable debug mode
        """
        pass
    
    @abstractmethod
    def add_route(
        self,
        path: str,
        endpoint: Callable,
        methods: List[str],
        name: Optional[str] = None
    ) -> None:
        """
        Add an HTTP route to the application.
        
        Args:
            path: URL path pattern (e.g., "/users/{user_id}")
            endpoint: Async function that handles the request
            methods: List of HTTP methods (["GET"], ["POST"], etc.)
            name: Optional route name for reverse URL lookup
        """
        pass
    
    @abstractmethod
    def add_websocket_route(
        self,
        path: str,
        endpoint: Callable,
        name: Optional[str] = None
    ) -> None:
        """
        Add a WebSocket route to the application.
        
        Args:
            path: URL path pattern (e.g., "/ws/{room_id}")
            endpoint: Async function that handles the WebSocket connection
            name: Optional route name
        """
        pass
    
    @abstractmethod
    def add_middleware(self, middleware_class: type, **options) -> None:
        """
        Add middleware to the application stack.
        
        Args:
            middleware_class: Middleware class (ASGI middleware protocol)
            **options: Keyword arguments passed to middleware constructor
        """
        pass
    
    @abstractmethod
    async def __call__(self, scope: Dict, receive: Callable, send: Callable):
        """
        ASGI application callable.
        
        Args:
            scope: ASGI scope dict (type, path, headers, etc.)
            receive: ASGI receive callable for getting messages
            send: ASGI send callable for sending messages
        """
        pass
    
    @abstractmethod
    def get_routes(self) -> List[Any]:
        """
        Get list of registered routes.
        
        Returns:
            List of route objects
        """
        pass
    
    @abstractmethod
    def get_state(self) -> Any:
        """
        Get application state object.
        
        Returns:
            State object for storing app-wide data
        """
        pass


class RequestAdapter(ABC):
    """
    Abstract adapter for HTTP Request objects.
    
    Wraps Starlette Request or tachyon-engine Request and provides
    a unified interface for accessing request data.
    """
    
    @abstractmethod
    def __init__(self, native_request: Any):
        """
        Initialize request adapter.
        
        Args:
            native_request: Native request object (Starlette Request or tachyon-engine Request)
        """
        pass
    
    @property
    @abstractmethod
    def method(self) -> str:
        """HTTP method (GET, POST, PUT, DELETE, etc.)"""
        pass
    
    @property
    @abstractmethod
    def url(self) -> str:
        """Full URL string"""
        pass
    
    @property
    @abstractmethod
    def path(self) -> str:
        """URL path without query string"""
        pass
    
    @property
    @abstractmethod
    def headers(self) -> Dict[str, str]:
        """HTTP headers (case-insensitive)"""
        pass
    
    @property
    @abstractmethod
    def query_params(self) -> Dict[str, str]:
        """Query string parameters"""
        pass
    
    @property
    @abstractmethod
    def path_params(self) -> Dict[str, str]:
        """Path parameters extracted from route"""
        pass
    
    @property
    @abstractmethod
    def cookies(self) -> Dict[str, str]:
        """HTTP cookies"""
        pass
    
    @property
    @abstractmethod
    def state(self) -> Any:
        """Per-request state object"""
        pass
    
    @abstractmethod
    async def json(self) -> Any:
        """
        Parse request body as JSON.
        
        Returns:
            Parsed JSON data
        """
        pass
    
    @abstractmethod
    async def body(self) -> bytes:
        """
        Get raw request body as bytes.
        
        Returns:
            Raw body bytes
        """
        pass
    
    @abstractmethod
    async def form(self) -> Dict[str, Any]:
        """
        Parse form data (application/x-www-form-urlencoded or multipart/form-data).
        
        Returns:
            Form data dict
        """
        pass
    
    @abstractmethod
    def get_native(self) -> Any:
        """
        Get the underlying native request object.
        
        Returns:
            Starlette Request or tachyon-engine Request
        """
        pass


class ResponseAdapter(ABC):
    """
    Abstract adapter for HTTP Response objects.
    
    Wraps Starlette Response or tachyon-engine Response and provides
    a unified interface for creating responses.
    """
    
    @abstractmethod
    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: Optional[str] = None
    ):
        """
        Initialize response adapter.
        
        Args:
            content: Response body content
            status_code: HTTP status code
            headers: Response headers
            media_type: Content-Type header value
        """
        pass
    
    @abstractmethod
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
        """
        Set a cookie in the response.
        
        Args:
            key: Cookie name
            value: Cookie value
            max_age: Max age in seconds
            path: Cookie path
            domain: Cookie domain
            secure: Secure flag
            httponly: HttpOnly flag
            samesite: SameSite attribute (Strict, Lax, None)
        """
        pass
    
    @abstractmethod
    def get_native(self) -> Any:
        """
        Get the underlying native response object.
        
        Returns:
            Starlette Response or tachyon-engine Response
        """
        pass


class RouteAdapter(ABC):
    """
    Abstract adapter for Route objects.
    
    Wraps route definitions for different engines.
    """
    
    @abstractmethod
    def __init__(
        self,
        path: str,
        endpoint: Callable,
        methods: List[str],
        name: Optional[str] = None
    ):
        """
        Initialize route adapter.
        
        Args:
            path: URL path pattern
            endpoint: Handler function
            methods: HTTP methods
            name: Optional route name
        """
        pass
    
    @abstractmethod
    def get_native(self) -> Any:
        """
        Get the underlying native route object.
        
        Returns:
            Starlette Route or tachyon-engine Route
        """
        pass


class WebSocketAdapter(ABC):
    """
    Abstract adapter for WebSocket objects.
    
    Wraps Starlette WebSocket or tachyon-engine WebSocket.
    """
    
    @abstractmethod
    def __init__(self, native_websocket: Any):
        """
        Initialize WebSocket adapter.
        
        Args:
            native_websocket: Native WebSocket object
        """
        pass
    
    @abstractmethod
    async def accept(self) -> None:
        """Accept the WebSocket connection."""
        pass
    
    @abstractmethod
    async def send_text(self, data: str) -> None:
        """Send text message."""
        pass
    
    @abstractmethod
    async def send_json(self, data: Any) -> None:
        """Send JSON message."""
        pass
    
    @abstractmethod
    async def send_bytes(self, data: bytes) -> None:
        """Send binary message."""
        pass
    
    @abstractmethod
    async def receive_text(self) -> str:
        """Receive text message."""
        pass
    
    @abstractmethod
    async def receive_json(self) -> Any:
        """Receive JSON message."""
        pass
    
    @abstractmethod
    async def receive_bytes(self) -> bytes:
        """Receive binary message."""
        pass
    
    @abstractmethod
    async def close(self, code: int = 1000) -> None:
        """Close the WebSocket connection."""
        pass
    
    @property
    @abstractmethod
    def path_params(self) -> Dict[str, str]:
        """Path parameters from URL."""
        pass
    
    @property
    @abstractmethod
    def query_params(self) -> Dict[str, str]:
        """Query parameters from URL."""
        pass
    
    @abstractmethod
    def get_native(self) -> Any:
        """Get the underlying native WebSocket object."""
        pass


class MiddlewareAdapter(ABC):
    """
    Abstract adapter for Middleware.
    
    Wraps middleware classes for different engines.
    """
    
    @abstractmethod
    def __init__(self, middleware_class: type, **options):
        """
        Initialize middleware adapter.
        
        Args:
            middleware_class: Middleware class
            **options: Middleware options
        """
        pass
    
    @abstractmethod
    def get_native(self) -> Any:
        """Get the underlying native middleware object."""
        pass
