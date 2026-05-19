import pytest
from tests.helpers import create_client


@pytest.mark.asyncio
async def test_path_param_is_extracted_and_converted(app):
    async with create_client(app) as client:
        response = await client.get("/items/123")

    assert response.status_code == 200
    assert response.json() == {"item_id_received": 123, "type": "int"}


@pytest.mark.asyncio
async def test_path_param_with_invalid_type_returns_404(app):
    async with create_client(app) as client:
        response = await client.get("/items/abc")

    assert response.status_code == 404
