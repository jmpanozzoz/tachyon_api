"""Async HTTP execution runs lifespan in the same loop as database use."""
import pytest


@pytest.mark.asyncio
async def test_async_reference_flow(async_client):
    response = await async_client.post("/auth/register", json={"email": "async@example.com", "password": "synthetic-password", "full_name": "Async"})
    assert response.status_code == 200
    login = await async_client.post("/auth/login", json={"email": "async@example.com", "password": "synthetic-password"})
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"], "X-Correlation-Id": "test-correlation"}
    response = await async_client.get("/customers/me", headers=headers)
    assert response.status_code == 404
    assert response.headers["x-correlation-id"] == "test-correlation"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert (await async_client.get("/health/live")).status_code == 200
    assert (await async_client.get("/health/ready")).json()["database"] == "up"


@pytest.mark.asyncio
async def test_concurrent_idempotent_writes_share_one_durable_job(async_client, application):
    import asyncio
    from sqlalchemy import func, select
    from example.shared.models import Job, Verification
    response = await async_client.post("/auth/register", json={"email": "race@example.com", "password": "synthetic-password", "full_name": "Concurrent"})
    assert response.status_code == 200
    login = await async_client.post("/auth/login", json={"email": "race@example.com", "password": "synthetic-password"})
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    customer = await async_client.post("/customers/", headers=headers,
        json={"first_name": "Concurrent", "last_name": "Example", "email": "race@example.com"})
    data = {"customer_id": customer.json()["customer_id"]}
    results = await asyncio.gather(*(async_client.post("/verification/start", headers={**headers, "Idempotency-Key": "race"}, json=data) for _ in range(8)))
    assert all(result.status_code == 200 for result in results)
    assert len({result.json()["verification_id"] for result in results}) == 1
    async with application.state.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Job)) == 1
        assert await session.scalar(select(func.count()).select_from(Verification)) == 1
