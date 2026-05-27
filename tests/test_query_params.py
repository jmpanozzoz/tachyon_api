from typing import List

import pytest
from tachyon_api import Tachyon
from tests.helpers import create_client
from tachyon_api.params import Query
from tachyon_api.processing._extractors.query_list import MAX_QUERY_LIST_SIZE


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
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/search")
    def search_items(
        name: str = Query(...),  # Required query parameter
        limit: int = Query(10),
        is_active: bool = Query(False),
    ):
        return {"name": name, "limit": limit, "active": is_active}

    async with create_client(app) as client:
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
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/search")
    def search_items(
        name: str = Query(...),  # Required query parameter
        limit: int = Query(10),
        is_active: bool = Query(False),
    ):
        return {"name": name, "limit": limit, "active": is_active}

    async with create_client(app) as client:
        response = await client.get(url)

    # The framework now uses 422 for parameter validation errors
    assert response.status_code == 422
    assert expected_detail_part in response.text


@pytest.mark.asyncio
async def test_query_list_under_cap_succeeds():
    """List query params up to MAX_QUERY_LIST_SIZE items are accepted."""
    app = Tachyon()

    @app.get("/bulk")
    def bulk(ids: List[int] = Query(...)):
        return {"count": len(ids)}

    payload = ",".join(str(i) for i in range(MAX_QUERY_LIST_SIZE - 5))
    async with create_client(app) as client:
        response = await client.get(f"/bulk?ids={payload}")

    assert response.status_code == 200
    assert response.json() == {"count": MAX_QUERY_LIST_SIZE - 5}


@pytest.mark.asyncio
async def test_query_list_over_cap_rejected_with_422():
    """v1.2.993 DoS guard — list query params over MAX_QUERY_LIST_SIZE are rejected."""
    app = Tachyon()

    @app.get("/bulk")
    def bulk(ids: List[int] = Query(...)):
        return {"count": len(ids)}

    payload = ",".join(str(i) for i in range(MAX_QUERY_LIST_SIZE + 100))
    async with create_client(app) as client:
        response = await client.get(f"/bulk?ids={payload}")

    assert response.status_code == 422
    assert "exceeds maximum list size" in response.text
    assert str(MAX_QUERY_LIST_SIZE) in response.text
