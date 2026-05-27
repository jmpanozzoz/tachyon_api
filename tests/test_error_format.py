import pytest
from tachyon_api import Tachyon, Query
from tests.helpers import create_client
from tachyon_api.models import Struct


class Out(Struct):
    value: int


@pytest.mark.asyncio
async def test_422_validation_error_structure_for_query():
    app = Tachyon()

    @app.get("/items")
    def items(limit: int = Query(...)):
        return {"limit": limit}

    async with create_client(app) as client:
        response = await client.get("/items?limit=bad")

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data.get("code") == "VALIDATION_ERROR"
    assert "Invalid value for integer conversion" in response.text


@pytest.mark.asyncio
async def test_500_response_validation_error_structure():
    app = Tachyon()

    @app.get("/bad", response_model=Out)
    def bad():
        # Return wrong shape to force response_model validation error
        return {"value": "not-an-int"}

    async with create_client(app) as client:
        response = await client.get("/bad")

    assert response.status_code == 500
    data = response.json()
    assert data["success"] is False
    assert data.get("code") == "RESPONSE_VALIDATION_ERROR"
    # v1.2.0: internal error details no longer leak to the client (logged at WARNING instead)
    assert data["error"] == "Internal Server Error"


@pytest.mark.asyncio
async def test_global_unhandled_exception_is_structured_500():
    app = Tachyon()

    @app.get("/explode")
    def explode():
        raise RuntimeError("boom")

    async with create_client(app) as client:
        response = await client.get("/explode")

    assert response.status_code == 500
    data = response.json()
    assert data["success"] is False
    assert data.get("code") == "INTERNAL_SERVER_ERROR"
    # Do not leak internal exception details
    assert data.get("error") == "Internal Server Error"
    assert "boom" not in response.text
