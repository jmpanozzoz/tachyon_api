"""
Tests for Header() parameter extraction.

TDD: These tests are written BEFORE the implementation.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from tachyon_api import Tachyon
from tachyon_api.params import Header


@pytest.mark.asyncio
async def test_header_required_parameter():
    """
    Test that a required Header parameter is extracted correctly.
    """
    app = Tachyon()

    @app.get("/protected")
    def protected(authorization: str = Header(...)):
        return {"auth": authorization}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": "Bearer token123"}
        )

    assert response.status_code == 200
    assert response.json()["auth"] == "Bearer token123"


@pytest.mark.asyncio
async def test_header_missing_required_returns_422():
    """
    Test that missing required header returns 422.
    """
    app = Tachyon()

    @app.get("/protected")
    def protected(authorization: str = Header(...)):
        return {"auth": authorization}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/protected")

    assert response.status_code == 422
    assert "authorization" in response.text.lower() or "header" in response.text.lower()


@pytest.mark.asyncio
async def test_header_optional_with_default():
    """
    Test that optional header uses default value when not provided.
    """
    app = Tachyon()

    @app.get("/info")
    def get_info(x_request_id: str = Header("default-id")):
        return {"request_id": x_request_id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Without header
        response = await client.get("/info")
        assert response.status_code == 200
        assert response.json()["request_id"] == "default-id"

        # With header
        response = await client.get("/info", headers={"X-Request-Id": "custom-123"})
        assert response.status_code == 200
        assert response.json()["request_id"] == "custom-123"


@pytest.mark.asyncio
async def test_header_case_insensitive():
    """
    Test that header names are case-insensitive (HTTP standard).
    """
    app = Tachyon()

    @app.get("/check")
    def check(x_custom_header: str = Header(...)):
        return {"value": x_custom_header}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Lowercase
        response = await client.get("/check", headers={"x-custom-header": "value1"})
        assert response.status_code == 200
        assert response.json()["value"] == "value1"

        # Mixed case
        response = await client.get("/check", headers={"X-Custom-Header": "value2"})
        assert response.status_code == 200
        assert response.json()["value"] == "value2"


@pytest.mark.asyncio
async def test_header_with_underscore_converts_to_hyphen():
    """
    Test that parameter names with underscores are matched to headers with hyphens.
    Python uses underscores, HTTP uses hyphens.
    """
    app = Tachyon()

    @app.get("/api")
    def api_call(x_api_key: str = Header(...)):
        return {"key": x_api_key}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api", headers={"X-API-Key": "secret123"})

    assert response.status_code == 200
    assert response.json()["key"] == "secret123"


@pytest.mark.asyncio
async def test_header_with_alias():
    """
    Test that Header can use an alias for custom header name.
    """
    app = Tachyon()

    @app.get("/custom")
    def custom(token: str = Header(..., alias="X-Auth-Token")):
        return {"token": token}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/custom", headers={"X-Auth-Token": "my-token"})

    assert response.status_code == 200
    assert response.json()["token"] == "my-token"


@pytest.mark.asyncio
async def test_multiple_headers():
    """
    Test that multiple headers can be extracted in a single endpoint.
    """
    app = Tachyon()

    @app.get("/multi")
    def multi(
        authorization: str = Header(...),
        x_request_id: str = Header("none"),
        accept_language: str = Header("en"),
    ):
        return {
            "auth": authorization,
            "request_id": x_request_id,
            "lang": accept_language,
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/multi",
            headers={
                "Authorization": "Bearer xyz",
                "X-Request-Id": "req-456",
                "Accept-Language": "es",
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data["auth"] == "Bearer xyz"
    assert data["request_id"] == "req-456"
    assert data["lang"] == "es"


@pytest.mark.asyncio
async def test_header_openapi_schema():
    """
    Test that Header parameters appear in OpenAPI schema.
    """
    app = Tachyon()

    @app.get("/secure")
    def secure(authorization: str = Header(..., description="Bearer token")):
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    
    # Check that the path exists and has parameters
    path_info = schema["paths"].get("/secure", {}).get("get", {})
    params = path_info.get("parameters", [])
    
    # Find the authorization header parameter
    auth_param = next((p for p in params if p["name"] == "authorization"), None)
    assert auth_param is not None
    assert auth_param["in"] == "header"
    assert auth_param["required"] is True
    assert auth_param.get("description") == "Bearer token"
