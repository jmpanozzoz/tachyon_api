"""
Tests for Depends(callable) - Factory dependencies support.

TDD: These tests are written BEFORE the implementation.

Currently Depends() only works with classes registered via @injectable.
This feature adds support for:
- Depends(function) - call a function to get the dependency value
- Depends(lambda) - inline factory functions
- Async function support
"""

import pytest
from httpx import AsyncClient, ASGITransport

from tachyon_api import Tachyon, Depends
from tachyon_api.params import Header


# --- Test fixtures (functions to be used as dependencies) ---


def get_db_connection():
    """Simulates getting a database connection."""
    return {"type": "postgres", "connected": True}


def get_current_user():
    """Simulates getting the current user."""
    return {"id": 1, "name": "John Doe"}


async def get_async_service():
    """Async dependency factory."""
    return {"service": "async_service", "ready": True}


def get_settings():
    """Returns app settings."""
    return {"debug": True, "version": "1.0.0"}


# --- Tests ---


@pytest.mark.asyncio
async def test_depends_with_sync_function():
    """
    Test that Depends() works with a regular sync function.
    """
    app = Tachyon()

    @app.get("/db")
    def check_db(db=Depends(get_db_connection)):
        return {"db_type": db["type"], "connected": db["connected"]}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/db")

    assert response.status_code == 200
    data = response.json()
    assert data["db_type"] == "postgres"
    assert data["connected"] is True


@pytest.mark.asyncio
async def test_depends_with_async_function():
    """
    Test that Depends() works with an async function.
    """
    app = Tachyon()

    @app.get("/service")
    async def check_service(svc=Depends(get_async_service)):
        return {"service": svc["service"], "ready": svc["ready"]}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/service")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "async_service"
    assert data["ready"] is True


@pytest.mark.asyncio
async def test_depends_with_lambda():
    """
    Test that Depends() works with a lambda function.
    """
    app = Tachyon()

    @app.get("/config")
    def get_config(config=Depends(lambda: {"env": "test", "port": 8000})):
        return config

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/config")

    assert response.status_code == 200
    data = response.json()
    assert data["env"] == "test"
    assert data["port"] == 8000


@pytest.mark.asyncio
async def test_depends_multiple_callables():
    """
    Test that multiple Depends(callable) work together.
    """
    app = Tachyon()

    @app.get("/status")
    def get_status(
        db=Depends(get_db_connection),
        user=Depends(get_current_user),
        settings=Depends(get_settings),
    ):
        return {
            "db_connected": db["connected"],
            "user_name": user["name"],
            "debug": settings["debug"],
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/status")

    assert response.status_code == 200
    data = response.json()
    assert data["db_connected"] is True
    assert data["user_name"] == "John Doe"
    assert data["debug"] is True


@pytest.mark.asyncio
async def test_depends_callable_with_other_params():
    """
    Test that Depends(callable) works alongside Query, Header, etc.
    """
    app = Tachyon()

    from tachyon_api.params import Query

    @app.get("/search")
    def search(
        q: str = Query(...),
        authorization: str = Header("anonymous"),
        user=Depends(get_current_user),
    ):
        return {
            "query": q,
            "auth": authorization,
            "searched_by": user["name"],
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/search?q=tachyon", headers={"Authorization": "Bearer token"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "tachyon"
    assert data["auth"] == "Bearer token"
    assert data["searched_by"] == "John Doe"


@pytest.mark.asyncio
async def test_depends_nested_callables():
    """
    Test that dependencies can depend on other dependencies (nested).
    """
    app = Tachyon()

    def get_db():
        return {"connection": "active"}

    def get_user_repo(db=Depends(get_db)):
        return {"repo": "users", "db": db}

    @app.get("/repo")
    def check_repo(repo=Depends(get_user_repo)):
        return {
            "repo_name": repo["repo"],
            "db_status": repo["db"]["connection"],
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/repo")

    assert response.status_code == 200
    data = response.json()
    assert data["repo_name"] == "users"
    assert data["db_status"] == "active"


@pytest.mark.asyncio
async def test_depends_callable_caching():
    """
    Test that the same dependency is only called once per request.
    """
    call_count = 0

    def counted_dependency():
        nonlocal call_count
        call_count += 1
        return {"count": call_count}

    app = Tachyon()

    @app.get("/count")
    def get_count(
        dep1=Depends(counted_dependency),
        dep2=Depends(counted_dependency),
    ):
        # Both should receive the same instance (cached)
        return {"dep1": dep1["count"], "dep2": dep2["count"]}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        call_count = 0  # Reset before request
        response = await client.get("/count")

    assert response.status_code == 200
    data = response.json()
    # Same dependency should be called only once and reused
    assert data["dep1"] == data["dep2"]
    assert call_count == 1  # Called only once, not twice
