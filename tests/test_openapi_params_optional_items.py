from httpx import AsyncClient, ASGITransport
from typing import Optional, List
import pytest

from tachyon_api import Tachyon, Query


@pytest.mark.asyncio
async def test_openapi_query_list_of_optional_items():
    app = Tachyon()

    @app.get("/opt")
    def get_opt(items: List[Optional[int]] = Query(...)):
        return {"items": items}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        schema = (await client.get("/openapi.json")).json()

    op = schema["paths"]["/opt"]["get"]
    assert "parameters" in op
    p = [p for p in op["parameters"] if p["name"] == "items" and p["in"] == "query"][0]
    assert p["schema"]["type"] == "array"
    assert p["schema"]["items"]["type"] == "integer"
    assert p["schema"]["items"]["nullable"] is True
