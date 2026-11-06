"""Durability, idempotency, leases and retry are checked against PostgreSQL."""
from datetime import timedelta
import pytest
from sqlalchemy import select
from example.shared.models import Event, Job, Verification, now
from example.modules.verification.jobs import claim, process, publish_one
from .conftest import register


def start(client, customer, auth_headers, key="unique-key", kind="standard"):
    return client.post("/verification/start", headers={**auth_headers, "Idempotency-Key": key},
                       json={"customer_id": customer["customer_id"], "verification_type": kind})


@pytest.mark.parametrize("kind,count", [("standard", 3), ("enhanced", 5)])
def test_durable_worker_completes_and_publishes(client, customer, auth_headers, kind, count):
    result = start(client, customer, auth_headers, kind=kind)
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["status"] == "pending" and len(value["checks"]) == count
    async def run():
        state = client.app.state
        claimed = await claim(state.sessions, state.settings)
        assert claimed[0] == value["verification_id"]
        assert await process(state.sessions, state.settings, claimed)
        assert not await process(state.sessions, state.settings, claimed)
        assert await publish_one(state.sessions, state.cache)
        assert not await publish_one(state.sessions, state.cache)
        async with state.sessions() as session:
            assert (await session.get(Job, claimed[0])).state == "done"
            assert len((await session.scalars(select(Event))).all()) == 1
    client.portal.call(run)
    response = client.get("/verification/" + value["verification_id"], headers=auth_headers)
    assert response.json()["status"] == "verified"
    assert client.get("/customers/" + customer["customer_id"], headers=auth_headers).json()["kyc_status"] == "verified"


def test_idempotency_and_input_conflicts(client, customer, auth_headers):
    first = start(client, customer, auth_headers)
    assert first.status_code == 200
    assert start(client, customer, auth_headers).json() == first.json()
    assert start(client, customer, auth_headers, kind="enhanced").status_code == 409
    assert start(client, customer, auth_headers, key="different", kind="unknown").status_code == 422
    assert client.post("/verification/start", headers=auth_headers, json={"customer_id": customer["customer_id"]}).status_code == 422


def test_verifications_enforce_ownership(client, customer, auth_headers):
    result = start(client, customer, auth_headers).json()
    _, other = register(client, "bob")
    assert start(client, customer, other).status_code == 404
    assert client.get("/verification/" + result["verification_id"], headers=other).status_code == 404
    assert client.get("/verification/missing", headers=other).status_code == 404


def test_expired_lease_is_reclaimed_and_old_worker_is_fenced(client, customer, auth_headers):
    assert start(client, customer, auth_headers).status_code == 200
    async def exercise():
        state = client.app.state
        first = await claim(state.sessions, state.settings)
        assert await claim(state.sessions, state.settings) is None
        async with state.sessions() as session, session.begin():
            (await session.get(Job, first[0])).lease_until = now() - timedelta(seconds=1)
        second = await claim(state.sessions, state.settings)
        assert second[0] == first[0] and second[1] != first[1]
        assert not await process(state.sessions, state.settings, first)
        assert await process(state.sessions, state.settings, second)
    client.portal.call(exercise)


def test_timeout_retries_then_fails_durably(client, customer, auth_headers):
    assert start(client, customer, auth_headers).status_code == 200
    async def exercise():
        state = client.app.state
        state.settings.provider_result = "timeout"
        state.settings.job_max_attempts = 2
        first = await claim(state.sessions, state.settings)
        assert not await process(state.sessions, state.settings, first)
        assert await claim(state.sessions, state.settings) is None
        async with state.sessions() as session, session.begin():
            (await session.get(Job, first[0])).available_at = now() - timedelta(seconds=1)
        second = await claim(state.sessions, state.settings)
        assert not await process(state.sessions, state.settings, second)
        async with state.sessions() as session:
            assert (await session.get(Job, first[0])).state == "failed"
            assert (await session.get(Verification, first[0])).status == "failed"
    client.portal.call(exercise)


@pytest.mark.parametrize("reason", ["expired", "attempts"])
def test_unrecoverable_jobs_finish_with_explicit_status(client, customer, auth_headers, reason):
    value = start(client, customer, auth_headers).json()
    async def exercise():
        state = client.app.state
        async with state.sessions() as session, session.begin():
            if reason == "expired":
                (await session.get(Verification, value["verification_id"])).expires_at = now() - timedelta(seconds=1)
            else:
                (await session.get(Job, value["verification_id"])).attempts = state.settings.job_max_attempts
        assert await claim(state.sessions, state.settings) is None
        async with state.sessions() as session:
            job = await session.get(Job, value["verification_id"])
            assert job.state == "failed"
            status = (await session.get(Verification, value["verification_id"])).status
            assert status == ("expired" if reason == "expired" else "failed")
    client.portal.call(exercise)


def test_rejected_provider_result_is_deterministic(client, customer, auth_headers):
    value = start(client, customer, auth_headers).json()
    async def exercise():
        state = client.app.state
        state.settings.provider_result = "failed"
        assert await process(state.sessions, state.settings, await claim(state.sessions, state.settings))
    client.portal.call(exercise)
    response = client.get("/verification/" + value["verification_id"], headers=auth_headers).json()
    assert response["status"] == "rejected"
    assert response["risk_score"] == 100


def test_outbox_retry_preserves_event_when_redis_fails(client, customer, auth_headers, monkeypatch):
    from unittest.mock import AsyncMock
    from redis.exceptions import ConnectionError
    value = start(client, customer, auth_headers).json()
    async def exercise():
        state = client.app.state
        assert await process(state.sessions, state.settings, await claim(state.sessions, state.settings))
        original = state.redis.publish
        monkeypatch.setattr(state.redis, "publish", AsyncMock(side_effect=ConnectionError("offline")))
        with pytest.raises(ConnectionError):
            await publish_one(state.sessions, state.cache)
        async with state.sessions() as session:
            event = await session.scalar(select(Event))
            assert event.payload["verification_id"] == value["verification_id"] and not event.published
        monkeypatch.setattr(state.redis, "publish", original)
        assert await publish_one(state.sessions, state.cache)
    client.portal.call(exercise)
