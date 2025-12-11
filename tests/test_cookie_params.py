"""
Tests for Cookie() parameter extraction.

TDD: These tests are written BEFORE the implementation (Cookie already implemented with Header).
"""

import pytest
from httpx import AsyncClient, ASGITransport

from tachyon_api import Tachyon
from tachyon_api.params import Cookie


@pytest.mark.asyncio
async def test_cookie_required_parameter():
    """
    Test that a required Cookie parameter is extracted correctly.
    """
    app = Tachyon()

    @app.get("/profile")
    def profile(session_id: str = Cookie(...)):
        return {"session": session_id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/profile", cookies={"session_id": "abc123"})

    assert response.status_code == 200
    assert response.json()["session"] == "abc123"


@pytest.mark.asyncio
async def test_cookie_missing_required_returns_422():
    """
    Test that missing required cookie returns 422.
    """
    app = Tachyon()

    @app.get("/profile")
    def profile(session_id: str = Cookie(...)):
        return {"session": session_id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/profile")

    assert response.status_code == 422
    assert "session_id" in response.text.lower() or "cookie" in response.text.lower()


@pytest.mark.asyncio
async def test_cookie_optional_with_default():
    """
    Test that optional cookie uses default value when not provided.
    """
    app = Tachyon()

    @app.get("/prefs")
    def get_prefs(theme: str = Cookie("light")):
        return {"theme": theme}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Without cookie
        response = await client.get("/prefs")
        assert response.status_code == 200
        assert response.json()["theme"] == "light"

        # With cookie
        response = await client.get("/prefs", cookies={"theme": "dark"})
        assert response.status_code == 200
        assert response.json()["theme"] == "dark"


@pytest.mark.asyncio
async def test_cookie_with_alias():
    """
    Test that Cookie can use an alias for custom cookie name.
    """
    app = Tachyon()

    @app.get("/session")
    def session(token: str = Cookie(..., alias="auth_token")):
        return {"token": token}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/session", cookies={"auth_token": "xyz789"})

    assert response.status_code == 200
    assert response.json()["token"] == "xyz789"


@pytest.mark.asyncio
async def test_cookie_openapi_schema():
    """
    Test that Cookie parameters appear in OpenAPI schema.
    """
    app = Tachyon()

    @app.get("/check")
    def check(session: str = Cookie(..., description="Session cookie")):
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    
    path_info = schema["paths"].get("/check", {}).get("get", {})
    params = path_info.get("parameters", [])
    
    session_param = next((p for p in params if p["name"] == "session"), None)
    assert session_param is not None
    assert session_param["in"] == "cookie"
    assert session_param["required"] is True
    assert session_param.get("description") == "Session cookie"
