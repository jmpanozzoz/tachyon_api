# HOT PATH — Tachyon's ASGI entry point. Lazily builds the HTTP app on first
# request (middleware stack is mutable until then) and delegates by scope type.

from typing import Callable


class ASGIEntry:
    """Tachyon's __call__ — the ASGI callable surface."""

    __slots__ = ("_app",)

    def __init__(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        scope["app"] = self._app  # required by Starlette middleware protocol

        app = self._app

        if not app._docs_routes.setup_done:
            app._docs_routes.setup()

        if scope["type"] == "http":
            if app._http_app is None:
                app._http_app = self._build_http_app()
            await app._http_app(scope, receive, send)
        else:
            # WebSocket routing and lifespan need Starlette's full stack
            await app._router(scope, receive, send)

    def _build_http_app(self) -> Callable:
        """User middlewares → TachyonDispatcher (no Starlette overhead for HTTP)."""
        return self._app._mw_stack.build(self._app._dispatcher)
