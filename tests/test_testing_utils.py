"""
Tests for Testing Utilities (TDD).
Release 0.6.7 - Testing Utilities
"""

import pytest


# =============================================================================
# TachyonTestClient Tests
# =============================================================================


class TestTachyonTestClient:
    """Tests for TachyonTestClient."""

    def test_client_get_request(self):
        """Should make GET requests."""
        from tachyon_api import Tachyon
        from tachyon_api.testing import TachyonTestClient

        app = Tachyon()

        @app.get("/hello")
        def hello():
            return {"message": "Hello, World!"}

        client = TachyonTestClient(app)
        response = client.get("/hello")

        assert response.status_code == 200
        assert response.json() == {"message": "Hello, World!"}

    def test_client_post_request(self):
        """Should make POST requests with JSON body."""
        from tachyon_api import Tachyon, Struct, Body
        from tachyon_api.testing import TachyonTestClient

        app = Tachyon()

        class Item(Struct):
            name: str
            price: float

        @app.post("/items")
        def create_item(item: Item = Body(...)):
            return {"name": item.name, "price": item.price}

        client = TachyonTestClient(app)
        response = client.post("/items", json={"name": "Widget", "price": 9.99})

        assert response.status_code == 200
        assert response.json() == {"name": "Widget", "price": 9.99}

    def test_client_with_headers(self):
        """Should send custom headers."""
        from tachyon_api import Tachyon, Header
        from tachyon_api.testing import TachyonTestClient

        app = Tachyon()

        @app.get("/auth")
        def auth(authorization: str = Header(...)):
            return {"auth": authorization}

        client = TachyonTestClient(app)
        response = client.get("/auth", headers={"Authorization": "Bearer token123"})

        assert response.status_code == 200
        assert response.json() == {"auth": "Bearer token123"}

    def test_client_with_query_params(self):
        """Should send query parameters."""
        from tachyon_api import Tachyon, Query
        from tachyon_api.testing import TachyonTestClient

        app = Tachyon()

        @app.get("/search")
        def search(q: str = Query(...), limit: int = Query(10)):
            return {"query": q, "limit": limit}

        client = TachyonTestClient(app)
        response = client.get("/search", params={"q": "test", "limit": 5})

        assert response.status_code == 200
        assert response.json() == {"query": "test", "limit": 5}

    def test_client_with_cookies(self):
        """Should send cookies."""
        from tachyon_api import Tachyon, Cookie
        from tachyon_api.testing import TachyonTestClient

        app = Tachyon()

        @app.get("/session")
        def session(session_id: str = Cookie(...)):
            return {"session": session_id}

        client = TachyonTestClient(app)
        client.cookies.set("session_id", "abc123")
        response = client.get("/session")

        assert response.status_code == 200
        assert response.json() == {"session": "abc123"}

    def test_client_context_manager(self):
        """Should work as context manager."""
        from tachyon_api import Tachyon
        from tachyon_api.testing import TachyonTestClient

        app = Tachyon()

        @app.get("/test")
        def test_endpoint():
            return {"ok": True}

        with TachyonTestClient(app) as client:
            response = client.get("/test")
            assert response.status_code == 200


# =============================================================================
# Dependency Overrides Tests
# =============================================================================


class TestDependencyOverrides:
    """Tests for dependency_overrides functionality."""

    def test_override_injectable_class(self):
        """Should override @injectable dependencies."""
        from tachyon_api import Tachyon, injectable, Depends
        from tachyon_api.testing import TachyonTestClient

        @injectable
        class RealDatabase:
            def get_user(self):
                return "real_user"

        class MockDatabase:
            def get_user(self):
                return "mock_user"

        app = Tachyon()

        @app.get("/user")
        def get_user(db: RealDatabase = Depends()):
            return {"user": db.get_user()}

        # Without override - should use real
        client = TachyonTestClient(app)
        response = client.get("/user")
        assert response.json() == {"user": "real_user"}

        # With override - should use mock
        app.dependency_overrides[RealDatabase] = MockDatabase
        response = client.get("/user")
        assert response.json() == {"user": "mock_user"}

        # Clear overrides
        app.dependency_overrides.clear()
        response = client.get("/user")
        assert response.json() == {"user": "real_user"}

    def test_override_callable_dependency(self):
        """Should override Depends(callable) dependencies."""
        from tachyon_api import Tachyon, Depends
        from tachyon_api.testing import TachyonTestClient

        def get_api_key():
            return "real_api_key"

        def mock_api_key():
            return "mock_api_key"

        app = Tachyon()

        @app.get("/api")
        def api_endpoint(api_key: str = Depends(get_api_key)):
            return {"api_key": api_key}

        client = TachyonTestClient(app)

        # Without override
        response = client.get("/api")
        assert response.json() == {"api_key": "real_api_key"}

        # With override
        app.dependency_overrides[get_api_key] = mock_api_key
        response = client.get("/api")
        assert response.json() == {"api_key": "mock_api_key"}

    def test_override_with_lambda(self):
        """Should override with lambda functions."""
        from tachyon_api import Tachyon, injectable, Depends
        from tachyon_api.testing import TachyonTestClient

        @injectable
        class ConfigService:
            def get_env(self):
                return "production"

        app = Tachyon()

        @app.get("/env")
        def get_env(config: ConfigService = Depends()):
            return {"env": config.get_env()}

        client = TachyonTestClient(app)

        # Override with lambda that returns mock object
        class MockConfig:
            def get_env(self):
                return "test"

        app.dependency_overrides[ConfigService] = lambda: MockConfig()
        response = client.get("/env")
        assert response.json() == {"env": "test"}

    def test_multiple_overrides(self):
        """Should handle multiple dependency overrides."""
        from tachyon_api import Tachyon, injectable, Depends
        from tachyon_api.testing import TachyonTestClient

        @injectable
        class ServiceA:
            def value(self):
                return "A"

        @injectable
        class ServiceB:
            def value(self):
                return "B"

        app = Tachyon()

        @app.get("/combined")
        def combined(a: ServiceA = Depends(), b: ServiceB = Depends()):
            return {"a": a.value(), "b": b.value()}

        client = TachyonTestClient(app)

        class MockA:
            def value(self):
                return "MockA"

        class MockB:
            def value(self):
                return "MockB"

        app.dependency_overrides[ServiceA] = MockA
        app.dependency_overrides[ServiceB] = MockB

        response = client.get("/combined")
        assert response.json() == {"a": "MockA", "b": "MockB"}


# =============================================================================
# Async Client Tests
# =============================================================================


class TestAsyncClient:
    """Tests for async testing support."""

    @pytest.mark.asyncio
    async def test_async_client(self):
        """Should support async testing."""
        from tachyon_api import Tachyon
        from tachyon_api.testing import AsyncTachyonTestClient

        app = Tachyon()

        @app.get("/async")
        async def async_endpoint():
            return {"async": True}

        async with AsyncTachyonTestClient(app) as client:
            response = await client.get("/async")
            assert response.status_code == 200
            assert response.json() == {"async": True}

    @pytest.mark.asyncio
    async def test_async_client_post(self):
        """Async client should handle POST requests."""
        from tachyon_api import Tachyon, Struct, Body
        from tachyon_api.testing import AsyncTachyonTestClient

        app = Tachyon()

        class Data(Struct):
            value: int

        @app.post("/data")
        async def post_data(data: Data = Body(...)):
            return {"received": data.value}

        async with AsyncTachyonTestClient(app) as client:
            response = await client.post("/data", json={"value": 42})
            assert response.status_code == 200
            assert response.json() == {"received": 42}
