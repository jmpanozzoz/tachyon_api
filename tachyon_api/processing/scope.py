"""Lazy request metadata with one bounded, shared Starlette body stream."""
from __future__ import annotations

from typing import Any
from contextlib import AsyncExitStack
import logging
import sys

from anyio import CancelScope, fail_after
from starlette.datastructures import Headers, QueryParams
from starlette.requests import cookie_parser
from ._request import ManagedRequest

from ._body_errors import RequestBodyTooLarge


DEPENDENCY_CLEANUP_TIMEOUT = 10


class TachyonScope:
    __slots__ = (
        "_scope", "_receive", "_send", "_query_params", "_headers", "_cookies",
        "_request", "_received_bytes", "_max_body_size", "_dependency_stack", "_dependency_error",
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
        self._dependency_stack = None
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

    def _check_body_limit(self):
        size = self._received_bytes
        if self._received_bytes == 0:
            content_length = self.headers.get("content-length")
            if content_length is not None:
                try:
                    size = int(content_length)
                except ValueError:
                    pass
        if size > self._max_body_size:
            self._scope["_tachyon_body_rejected"] = True
            raise RequestBodyTooLarge(f"Request body too large (max {self._max_body_size} bytes)")

    async def _bounded_receive(self):
        self._check_body_limit()
        message = await self._receive()
        if message["type"] == "http.request":
            self._received_bytes += len(message.get("body", b""))
            if self._received_bytes > self._max_body_size:
                self._check_body_limit()
        return message

    async def body(self):
        # Reject declared oversize before creating a Request and its cleanup scope.
        # The receive path uses the same guard for direct Request/form/file reads.
        self._check_body_limit()
        return await self.as_request().body()

    async def form(self):
        return await self.as_request().form()

    async def enter_dependency(self, manager):
        if self._dependency_stack is None:
            self._dependency_stack = AsyncExitStack()
            self._dependency_error = None
        return await self._dependency_stack.enter_async_context(manager)

    def dependency_failed(self, exc):
        if self._dependency_stack is not None:
            self._dependency_error = (type(exc), exc, exc.__traceback__)

    async def close(self):
        if self._dependency_stack is None and self._request is None:
            return
        exc_info = sys.exc_info()
        primary = exc_info if exc_info[0] is not None else getattr(self, "_dependency_error", None)
        stack, self._dependency_stack = self._dependency_stack, None
        self._dependency_error = None
        try:
            if stack is not None:
                try:
                    with fail_after(DEPENDENCY_CLEANUP_TIMEOUT, shield=True):
                        await stack.__aexit__(*(primary or (None, None, None)))
                except BaseException as cleanup_error:
                    if primary is None:
                        raise
                    # Never replace the endpoint, transport or cancellation error.
                    logging.getLogger("tachyon.dependencies").error("Dependency cleanup failed (%s)", type(cleanup_error).__name__)
        finally:
            if self._request is not None:
                with CancelScope(shield=True):
                    await self._request.close()

    def as_request(self):
        if self._request is None:
            self._request = ManagedRequest(self._scope, self._bounded_receive, self._send)
        return self._request
