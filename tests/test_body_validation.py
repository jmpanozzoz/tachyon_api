import pytest
from httpx import AsyncClient, ASGITransport
from tachyon_api import Tachyon
from tachyon_api.params import Body
from tachyon_api.models import Struct


class Item(Struct):
    """Test model for OpenAPI generation"""

    name: str
    price: float


@pytest.mark.asyncio
async def test_valid_body_is_processed():
    """
    Test that a valid body is processed correctly by the endpoint.
    """
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/items", json={"name": "Tachyon Core", "price": 99.99}
        )

    assert response.status_code == 200
    assert response.json()["item_name"] == "Tachyon Core"


@pytest.mark.asyncio
async def test_invalid_body_returns_422():
    """
    Test that an invalid body returns a 422 status code with validation errors.
    """
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/items", json={"name": "Defective Core", "price": "barato"}
        )

    assert response.status_code == 422
    assert "price" in response.text
    assert "str" in response.text
