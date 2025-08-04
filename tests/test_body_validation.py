import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_valid_body_is_processed(app):
    """
    Test that a valid body is processed correctly by the endpoint.
    """

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/items", json={"name": "Tachyon Core", "price": 99.99}
        )

    assert response.status_code == 200
    assert response.json()["item_name"] == "Tachyon Core"


@pytest.mark.asyncio
async def test_invalid_body_returns_422(app):
    """
    Test that an invalid body returns a 422 status code with validation errors.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/items", json={"name": "Defective Core", "price": "barato"}
        )

    assert response.status_code == 422
    assert "detail" in response.json()
