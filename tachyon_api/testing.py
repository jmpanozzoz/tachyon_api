"""Sync and async test clients for Tachyon applications."""

from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from starlette.testclient import TestClient
from httpx import AsyncClient, ASGITransport


class TachyonTestClient(TestClient):
    """Synchronous test client wrapping Starlette's TestClient."""

    def __init__(
        self,
        app,
        base_url: str = "http://test",
        raise_server_exceptions: bool = True,
        **kwargs,
    ):
        super().__init__(
            app,
            base_url=base_url,
            raise_server_exceptions=raise_server_exceptions,
            **kwargs,
        )


class AsyncTachyonTestClient:
    """Async context-manager wrapping httpx.AsyncClient with ASGITransport.

    Yields the underlying ``httpx.AsyncClient`` so all httpx features
    (cookies, auth, custom headers, follow_redirects, timeout, etc.) are
    available via constructor kwargs.

    Example::

        async with AsyncTachyonTestClient(app, headers={"X-Token": "test"}) as client:
            r = await client.get("/users/1")
    """

    def __init__(
        self,
        app,
        base_url: str = "http://testserver",
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        auth: Any = None,
        follow_redirects: bool = False,
        timeout: float = 5.0,
        **kwargs,
    ):
        self._app = app
        self._client_kwargs: Dict[str, Any] = {
            "transport": ASGITransport(app=app),
            "base_url": base_url,
            "follow_redirects": follow_redirects,
            "timeout": timeout,
            **kwargs,
        }
        if headers:
            self._client_kwargs["headers"] = headers
        if cookies:
            self._client_kwargs["cookies"] = cookies
        if auth is not None:
            self._client_kwargs["auth"] = auth
        self._client: Optional[AsyncClient] = None

    async def __aenter__(self) -> AsyncClient:
        self._client = AsyncClient(**self._client_kwargs)
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()


@asynccontextmanager
async def create_client(
    app,
    base_url: str = "http://testserver",
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    auth: Any = None,
    follow_redirects: bool = False,
    timeout: float = 5.0,
    **kwargs,
):
    """Async context manager that yields an ``httpx.AsyncClient`` bound to *app*.

    Canonical helper for Tachyon tests — mirrors the pattern used throughout
    the test suite.  All httpx options (cookies, auth, headers, timeouts,
    follow_redirects) are forwarded to the underlying client.

    Example::

        async with create_client(app) as client:
            r = await client.get("/healthz")
            assert r.status_code == 200
    """
    client_kwargs: Dict[str, Any] = {
        "transport": ASGITransport(app=app),
        "base_url": base_url,
        "follow_redirects": follow_redirects,
        "timeout": timeout,
        **kwargs,
    }
    if headers:
        client_kwargs["headers"] = headers
    if cookies:
        client_kwargs["cookies"] = cookies
    if auth is not None:
        client_kwargs["auth"] = auth

    async with AsyncClient(**client_kwargs) as client:
        yield client
