"""
Tests for Request object injection in endpoints.

TDD: These tests are written BEFORE the implementation.
"""

import pytest
from starlette.requests import Request
from tests.helpers import create_client

from tachyon_api import Tachyon


@pytest.mark.asyncio
async def test_request_object_is_injected_when_annotated():
    app = Tachyon()

    @app.get("/info")
    def get_info(request: Request):
        return {
            "method": request.method,
            "path": request.url.path,
        }

    async with create_client(app) as client:
        response = await client.get("/info")

    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "GET"
    assert data["path"] == "/info"


@pytest.mark.asyncio
async def test_request_injection_with_other_params():
    app = Tachyon()

    @app.get("/users/{user_id}")
    def get_user(user_id: int, request: Request):
        return {
            "user_id": user_id,
            "client_host": request.client.host if request.client else "unknown",
            "path": request.url.path,
        }

    async with create_client(app) as client:
        response = await client.get("/users/123")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 123
    assert data["path"] == "/users/123"


@pytest.mark.asyncio
async def test_request_injection_access_headers():
    app = Tachyon()

    @app.get("/headers")
    def get_headers(request: Request):
        return {
            "user_agent": request.headers.get("user-agent", "unknown"),
            "custom_header": request.headers.get("x-custom-header", "not-set"),
        }

    async with create_client(app) as client:
        response = await client.get(
            "/headers", headers={"X-Custom-Header": "test-value"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["custom_header"] == "test-value"


@pytest.mark.asyncio
async def test_request_injection_access_query_params():
    app = Tachyon()

    @app.get("/search")
    def search(request: Request):
        return {
            "query": request.query_params.get("q", ""),
            "page": request.query_params.get("page", "1"),
        }

    async with create_client(app) as client:
        response = await client.get("/search?q=tachyon&page=2")

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "tachyon"
    assert data["page"] == "2"


@pytest.mark.asyncio
async def test_request_injection_in_post_with_body():
    from tachyon_api.models import Struct
    from tachyon_api.params import Body

    app = Tachyon()

    class Item(Struct):
        name: str

    @app.post("/items")
    def create_item(item: Item = Body(), request: Request = None):
        return {
            "item_name": item.name,
            "method": request.method if request else "unknown",
            "content_type": request.headers.get("content-type", "") if request else "",
        }

    async with create_client(app) as client:
        response = await client.post("/items", json={"name": "Test Item"})

    assert response.status_code == 200
    data = response.json()
    assert data["item_name"] == "Test Item"
    assert data["method"] == "POST"
    assert "application/json" in data["content_type"]


@pytest.mark.asyncio
async def test_request_injected_even_with_none_default():
    """Request is always injected by the framework regardless of default value."""
    app = Tachyon()

    injected = {}

    @app.get("/probe")
    def probe(request: Request = None):
        injected["value"] = request
        return {"is_request": isinstance(request, Request)}

    async with create_client(app) as client:
        response = await client.get("/probe")

    assert response.status_code == 200
    assert response.json()["is_request"] is True
    assert injected["value"] is not None
