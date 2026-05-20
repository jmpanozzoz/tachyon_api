import uuid
import pytest
from tachyon_api import Tachyon
from tachyon_api.params import Path
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


@pytest.mark.asyncio
async def test_path_param_uuid():
    app = Tachyon()
    sample_id = uuid.uuid4()

    @app.get("/resources/{resource_id}")
    def get_resource(resource_id: uuid.UUID = Path()):
        return {"id": str(resource_id)}

    async with create_client(app) as client:
        response = await client.get(f"/resources/{sample_id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(sample_id)


@pytest.mark.asyncio
async def test_path_param_float():
    app = Tachyon()

    @app.get("/price/{value}")
    def get_price(value: float = Path()):
        return {"value": value}

    async with create_client(app) as client:
        response = await client.get("/price/3.14")

    assert response.status_code == 200
    assert response.json()["value"] == pytest.approx(3.14)
