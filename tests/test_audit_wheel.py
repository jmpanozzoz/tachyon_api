"""Behavior tests suitable for running against an installed wheel outside source."""

import httpx
import pytest

from tachyon_api import Body, Struct, Tachyon


@pytest.mark.asyncio
async def test_installed_wheel_validates_routes_and_serializes():
    app = Tachyon()

    class Payload(Struct):
        count: int

    @app.post("/items/{item_id}")
    async def item(item_id: int, payload: Payload = Body()):
        return {"item_id": item_id, "count": payload.count}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        valid = await client.post("/items/42", json={"count": 3})
        invalid = await client.post("/items/42", json={"count": "bad"})
    assert valid.status_code == 200
    assert valid.json() == {"item_id": 42, "count": 3}
    assert invalid.status_code == 422
