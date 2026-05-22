"""
TachyonScope — thin ASGI scope wrapper for the request hot path.

Replaces Starlette's Request in process_parameters. Identical lazy properties
but no class hierarchy, no __init__ assertions, and __slots__ for C-level
attribute storage (faster None checks, smaller per-object footprint).

call as_request() to get a full Starlette Request when explicitly needed:
  - KIND_REQUEST params (user declared `request: Request`)
  - Exception handlers that expect a Request
  - Form parsing (delegates to Starlette's multipart implementation)
"""
from __future__ import annotations

from http.cookies import SimpleCookie
from typing import Any

from starlette.datastructures import Headers, QueryParams
from starlette.requests import Request


class TachyonScope:
    __slots__ = (
        "_scope", "_receive", "_send",
        "_body", "_query_params", "_headers", "_cookies",
        "_form_data", "_request",
    )

    def __init__(self, scope: dict, receive: Any, send: Any) -> None:
        self._scope = scope
        self._receive = receive
        self._send = send
        self._body: bytes | None = None
        self._query_params = None
        self._headers = None
        self._cookies = None
        self._form_data = None
        self._request: Request | None = None

    # ── Properties read directly from scope / lazy-parsed ────────────────────

    @property
    def path_params(self) -> dict:
        return self._scope["path_params"]

    @property
    def query_params(self) -> QueryParams:
        if self._query_params is None:
            self._query_params = QueryParams(self._scope.get("query_string", b""))
        return self._query_params

    @property
    def headers(self) -> Headers:
        if self._headers is None:
            self._headers = Headers(scope=self._scope)
        return self._headers

    @property
    def cookies(self) -> dict:
        if self._cookies is None:
            cookies: dict = {}
            cookie_header = self.headers.get("cookie")
            if cookie_header:
                try:
                    sc = SimpleCookie(cookie_header)
                    for key, morsel in sc.items():
                        cookies[key] = morsel.value
                except Exception:
                    pass
            self._cookies = cookies
        return self._cookies

    # ── Async body / form ────────────────────────────────────────────────────

    async def body(self) -> bytes:
        if self._body is None:
            chunks = []
            while True:
                message = await self._receive()
                chunk = message.get("body", b"")
                if chunk:
                    chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            self._body = b"".join(chunks)
        return self._body

    async def form(self) -> Any:
        # Multipart/form-url-encoded parsing is complex — delegate to Starlette
        if self._form_data is None:
            self._form_data = await self.as_request().form()
        return self._form_data

    # ── Escape hatch ─────────────────────────────────────────────────────────

    def as_request(self) -> Request:
        """Lazily materialise a full Starlette Request — only when needed."""
        if self._request is None:
            self._request = Request(self._scope, self._receive, self._send)
        return self._request
