import pytest
from httpx import AsyncClient, ASGITransport
from tachyon_api import Tachyon
from tachyon_api.params import Query


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url, expected_json",
    [
        (
            "/search?name=TachyonCore&limit=5&is_active=true",
            {"name": "TachyonCore", "limit": 5, "active": True},
        ),
        (
            "/search?name=TachyonCore",
            {"name": "TachyonCore", "limit": 10, "active": False},
        ),
    ],
)
async def test_query_params_success_cases(url, expected_json):
    """Test cases for successful query parameter handling in Tachyon API."""
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/search")
    def search_items(
        name: str = Query(...),  # Required query parameter
        limit: int = Query(10),
        is_active: bool = Query(False),
    ):
        return {"name": name, "limit": limit, "active": is_active}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(url)

    assert response.status_code == 200
    assert response.json() == expected_json


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url, expected_detail_part",
    [
        ("/search?limit=20", "Missing required query parameter"),
        ("/search?name=core&limit=abc", "Invalid value for integer conversion"),
    ],
)
async def test_query_params_error_cases(url, expected_detail_part):
    """Test cases for error handling in query parameter processing."""
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/search")
    def search_items(
        name: str = Query(...),  # Required query parameter
        limit: int = Query(10),
        is_active: bool = Query(False),
    ):
        return {"name": name, "limit": limit, "active": is_active}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(url)

    # The framework now uses 422 for parameter validation errors
    assert response.status_code == 422
    assert expected_detail_part in response.text
