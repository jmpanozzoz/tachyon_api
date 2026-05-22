# HOT PATH — routes HTTP scopes to the Cython trie dispatcher and non-HTTP
# scopes (WebSocket, lifespan) to the Starlette router fallback.

from typing import Callable


class HTTPDispatcher:
    """Splits ASGI traffic between the trie dispatcher (HTTP) and Starlette (WS/lifespan)."""

    __slots__ = ("_dispatcher", "_fallback")

    def __init__(self, dispatcher: Callable, fallback: Callable) -> None:
        self._dispatcher = dispatcher
        self._fallback = fallback

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            await self._dispatcher(scope, receive, send)
        else:
            await self._fallback(scope, receive, send)
