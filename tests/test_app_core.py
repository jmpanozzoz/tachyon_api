import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_home_endpoint_returns_200_and_correct_payload(app):
    """
    Test that the home endpoint returns a 200 status code and the expected JSON payload.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Tachyon is running!"}
