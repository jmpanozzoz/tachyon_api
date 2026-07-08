from typing import List, Optional

import pytest
from tachyon_api import Tachyon
from tests.helpers import create_client
from tachyon_api.params import Body
from tachyon_api.models import Struct


class Item(Struct):
    """Test model for OpenAPI generation"""

    name: str
    price: float


@pytest.mark.asyncio
async def test_valid_body_is_processed():
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.post("/items")
    def create_item(item: Item = Body()):
        """Create a new item"""
        return {
            "message": "Item created",
            "item_name": item.name,
            "item_price": item.price,
        }

    async with create_client(app) as client:
        response = await client.post(
            "/items", json={"name": "Tachyon Core", "price": 99.99}
        )

    assert response.status_code == 200
    assert response.json()["item_name"] == "Tachyon Core"


@pytest.mark.asyncio
async def test_invalid_body_returns_422():
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.post("/items")
    def create_item(item: Item = Body()):
        """Create a new item"""
        return {
            "message": "Item created",
            "item_name": item.name,
            "item_price": item.price,
        }

    async with create_client(app) as client:
        response = await client.post(
            "/items", json={"name": "Defective Core", "price": "barato"}
        )

    assert response.status_code == 422
    assert "price" in response.text
    assert "str" in response.text


@pytest.mark.asyncio
async def test_empty_body_returns_422():
    app = Tachyon()

    @app.post("/items")
    def create_item(item: Item = Body()):
        return {"name": item.name}

    async with create_client(app) as client:
        response = await client.post("/items", content=b"", headers={"content-type": "application/json"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_body_missing_required_field_returns_422():
    app = Tachyon()

    @app.post("/items")
    def create_item(item: Item = Body()):
        return {"name": item.name, "price": item.price}

    async with create_client(app) as client:
        response = await client.post("/items", json={"name": "only name"})

    assert response.status_code == 422


class OrderItem(Struct):
    name: str
    qty: int


@pytest.mark.asyncio
async def test_body_list_of_structs_decodes():
    """`Body(List[ItemStruct])` should accept a JSON array and decode it."""
    app = Tachyon()

    @app.post("/items")
    def create_items(items: List[OrderItem] = Body(...)):
        return {"count": len(items), "names": [it.name for it in items]}

    async with create_client(app) as client:
        response = await client.post(
            "/items",
            json=[{"name": "a", "qty": 1}, {"name": "b", "qty": 2}],
        )

    assert response.status_code == 200
    assert response.json() == {"count": 2, "names": ["a", "b"]}


@pytest.mark.asyncio
async def test_body_list_of_structs_validation_error():
    """Invalid array item should still produce a 422 via msgspec validation."""
    app = Tachyon()

    @app.post("/items")
    def create_items(items: List[OrderItem] = Body(...)):
        return {"ok": True}

    async with create_client(app) as client:
        # `qty` is missing on the second item
        response = await client.post(
            "/items",
            json=[{"name": "a", "qty": 1}, {"name": "b"}],
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_body_optional_struct_decodes():
    """`Body(Optional[Struct])` is also supported by msgspec."""
    app = Tachyon()

    @app.post("/maybe")
    def maybe(item: Optional[OrderItem] = Body(...)):
        return {"received_null": item is None, "name": item.name if item else None}

    async with create_client(app) as client:
        response = await client.post("/maybe", json={"name": "a", "qty": 1})
        assert response.status_code == 200
        assert response.json() == {"received_null": False, "name": "a"}
