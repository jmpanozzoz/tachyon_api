import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_explicit_dependency_injection(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/di_explicit/123")

    assert response.status_code == 200
    assert response.json()["source"] == "mock_db"


@pytest.mark.asyncio
async def test_implicit_dependency_injection(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/di_implicit/456")

    assert response.status_code == 200
    assert response.json()["id"] == 456
    assert response.json()["source"] == "mock_db"
