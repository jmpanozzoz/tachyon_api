"""
Tachyon API Adapters Module

This module provides adapter interfaces and implementations for different ASGI engines.
Allows seamless switching between Starlette and tachyon-engine.
"""

from .base import (
    AsgiApplicationAdapter,
    RequestAdapter,
    ResponseAdapter,
    RouteAdapter,
    WebSocketAdapter,
    MiddlewareAdapter,
)
from .starlette_adapter import (
    StarletteApplicationAdapter,
    StarletteRequestAdapter,
    StarletteResponseAdapter,
    StarletteRouteAdapter,
    StarletteWebSocketAdapter,
    StarletteMiddlewareAdapter,
)

__all__ = [
    # Base interfaces
    "AsgiApplicationAdapter",
    "RequestAdapter",
    "ResponseAdapter",
    "RouteAdapter",
    "WebSocketAdapter",
    "MiddlewareAdapter",
    # Starlette adapters
    "StarletteApplicationAdapter",
    "StarletteRequestAdapter",
    "StarletteResponseAdapter",
    "StarletteRouteAdapter",
    "StarletteWebSocketAdapter",
    "StarletteMiddlewareAdapter",
]
