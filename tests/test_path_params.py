import uuid
from typing import List, Optional

import pytest
from tachyon_api import Tachyon
from tachyon_api.params import Path
from tests.helpers import create_client


@pytest.fixture
def app():
    """Minimal app fixture — only endpoints needed by the path-param tests."""
    tachyon_app = Tachyon()

    @tachyon_app.get("/items/{item_id}")
    def get_item(item_id: int = Path()):
        return {"item_id_received": item_id, "type": "int"}

    yield tachyon_app


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


@pytest.mark.asyncio
async def test_path_list_of_optional_items_runtime():
    app = Tachyon()

    @app.get("/p/{ids}")
    def get_p(ids: List[Optional[int]] = Path()):
        return {"ids": ids}

    async with create_client(app) as client:
        resp = await client.get("/p/1,,3,null,5,")
        assert resp.status_code == 200
        assert resp.json() == {"ids": [1, None, 3, None, 5, None]}

        bad = await client.get("/p/1,x,3")
        assert bad.status_code == 404
