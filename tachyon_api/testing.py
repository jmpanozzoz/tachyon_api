"""
Tachyon Testing Utilities

Provides test clients and utilities for testing Tachyon applications.
"""

from typing import Any, Dict, Optional
from starlette.testclient import TestClient
from httpx import AsyncClient, ASGITransport


class TachyonTestClient(TestClient):
    """
    Synchronous test client for Tachyon applications.

    A wrapper around Starlette's TestClient that provides a convenient
    interface for testing Tachyon applications.

    Example:
        from tachyon_api.testing import TachyonTestClient

        def test_hello():
            app = Tachyon()

            @app.get("/hello")
            def hello():
                return {"message": "Hello!"}

            client = TachyonTestClient(app)
            response = client.get("/hello")
            assert response.status_code == 200
            assert response.json() == {"message": "Hello!"}

    Note:
        For async testing, use AsyncTachyonTestClient instead.
    """

    def __init__(
        self,
        app,
        base_url: str = "http://test",
        raise_server_exceptions: bool = True,
        **kwargs
    ):
        """
        Initialize the test client.

        Args:
            app: The Tachyon application instance
            base_url: Base URL for requests (default: "http://test")
            raise_server_exceptions: Whether to raise exceptions from the app
            **kwargs: Additional arguments passed to TestClient
        """
        super().__init__(
            app,
            base_url=base_url,
            raise_server_exceptions=raise_server_exceptions,
            **kwargs
        )


class AsyncTachyonTestClient:
    """
    Async test client for Tachyon applications.

    Wraps httpx.AsyncClient with ASGITransport for async testing.

    Example:
        from tachyon_api.testing import AsyncTachyonTestClient

        @pytest.mark.asyncio
        async def test_hello():
            app = Tachyon()

            @app.get("/hello")
            async def hello():
                return {"message": "Hello!"}

            async with AsyncTachyonTestClient(app) as client:
                response = await client.get("/hello")
                assert response.status_code == 200
    """

    def __init__(
        self,
        app,
        base_url: str = "http://test",
        **kwargs
    ):
        """
        Initialize the async test client.

        Args:
            app: The Tachyon application instance
            base_url: Base URL for requests (default: "http://test")
            **kwargs: Additional arguments passed to AsyncClient
        """
        self._app = app
        self._base_url = base_url
        self._kwargs = kwargs
        self._client: Optional[AsyncClient] = None

    async def __aenter__(self) -> AsyncClient:
        """Enter async context manager."""
        self._client = AsyncClient(
            transport=ASGITransport(app=self._app),
            base_url=self._base_url,
            **self._kwargs
        )
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
