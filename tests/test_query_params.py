import pytest
from httpx import AsyncClient, ASGITransport


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
async def test_query_params_success_cases(app, url, expected_json):
    """Test cases for successful query parameter handling in Tachyon API."""
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
async def test_query_params_error_cases(app, url, expected_detail_part):
    """Test cases for error handling in query parameter processing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(url)

    assert response.status_code == 422
    assert expected_detail_part in response.json()["detail"]
