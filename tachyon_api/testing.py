"""Sync and async test clients for Tachyon applications."""

from typing import Optional
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
    """Async test client wrapping httpx.AsyncClient with ASGITransport."""

    def __init__(self, app, base_url: str = "http://test", **kwargs):
        self._app = app
        self._base_url = base_url
        self._kwargs = kwargs
        self._client: Optional[AsyncClient] = None

    async def __aenter__(self) -> AsyncClient:
        self._client = AsyncClient(
            transport=ASGITransport(app=self._app),
            base_url=self._base_url,
            **self._kwargs,
        )
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
