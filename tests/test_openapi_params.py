from httpx import AsyncClient, ASGITransport
from typing import Optional, List

from tachyon_api import Tachyon, Query, Path


async def _get_openapi(app: Tachyon):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        return resp.json()


def _find_param(schema: dict, path: str, method: str, name: str, where: str):
    params = schema["paths"][path][method]["parameters"]
    for p in params:
        if p["name"] == name and p["in"] == where:
            return p
    raise AssertionError(f"Param {name} in {where} not found")


import pytest


@pytest.mark.asyncio
async def test_openapi_query_optional_and_list():
    app = Tachyon()

    @app.get("/search")
    def search(q: Optional[str] = Query(None), ids: List[int] = Query(...)):
        return {"q": q, "ids": ids}

    schema = await _get_openapi(app)
    op = schema["paths"]["/search"]["get"]
    assert "parameters" in op

    p_q = _find_param(schema, "/search", "get", "q", "query")
    assert p_q["schema"]["type"] == "string"
    assert p_q["schema"]["nullable"] is True
    assert p_q["required"] is False

    p_ids = _find_param(schema, "/search", "get", "ids", "query")
    assert p_ids["required"] is True
    assert p_ids["schema"]["type"] == "array"
    assert p_ids["schema"]["items"]["type"] == "integer"


@pytest.mark.asyncio
async def test_openapi_path_list_param():
    app = Tachyon()

    @app.get("/items/{ids}")
    def get_items(ids: List[int] = Path()):
        return {"ids": ids}

    schema = await _get_openapi(app)
    p_ids = _find_param(schema, "/items/{ids}", "get", "ids", "path")
    assert p_ids["required"] is True
    assert p_ids["schema"]["type"] == "array"
    assert p_ids["schema"]["items"]["type"] == "integer"

