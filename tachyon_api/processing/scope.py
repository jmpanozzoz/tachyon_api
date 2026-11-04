"""Lazy request metadata with one bounded, shared Starlette body stream."""
from __future__ import annotations

from typing import Any

from anyio import CancelScope
from starlette.datastructures import Headers, QueryParams
from starlette.requests import cookie_parser
from ._request import ManagedRequest

from ._body_errors import RequestBodyTooLarge


class TachyonScope:
    __slots__ = (
        "_scope", "_receive", "_send", "_query_params", "_headers", "_cookies",
        "_request", "_received_bytes", "_max_body_size",
    )

    def __init__(self, scope: dict, receive: Any, send: Any) -> None:
        self._scope = scope
        self._receive = receive
        self._send = send
        self._query_params = None
        self._headers = None
        self._cookies = None
        self._request = None
        self._received_bytes = 0
        self._max_body_size = getattr(scope.get("app"), "max_body_size", 2 * 1024 * 1024)

    @property
    def path_params(self):
        return self._scope["path_params"]

    @property
    def query_params(self):
        if self._query_params is None:
            self._query_params = QueryParams(self._scope.get("query_string", b""))
        return self._query_params

    @property
    def headers(self):
        if self._headers is None:
            self._headers = Headers(scope=self._scope)
        return self._headers

    @property
    def cookies(self):
        if self._cookies is None:
            self._cookies = cookie_parser(self.headers.get("cookie", ""))
        return self._cookies

    async def _bounded_receive(self):
        if self._received_bytes == 0:
            content_length = self.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = 0
                if declared_size > self._max_body_size:
                    raise RequestBodyTooLarge(f"Request body too large (max {self._max_body_size} bytes)")
        if self._received_bytes > self._max_body_size:
            raise RequestBodyTooLarge(f"Request body too large (max {self._max_body_size} bytes)")
        message = await self._receive()
        if message["type"] == "http.request":
            self._received_bytes += len(message.get("body", b""))
            if self._received_bytes > self._max_body_size:
                raise RequestBodyTooLarge(f"Request body too large (max {self._max_body_size} bytes)")
        return message

    async def body(self):
        return await self.as_request().body()

    async def form(self):
        return await self.as_request().form()

    async def close(self):
        if self._request is not None:
            # File cleanup must complete even if response transmission is cancelled.
            with CancelScope(shield=True):
                await self._request.close()

    def as_request(self):
        if self._request is None:
            self._request = ManagedRequest(self._scope, self._bounded_receive, self._send)
        return self._request
