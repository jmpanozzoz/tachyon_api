"""Behavioral acceptance beyond happy-path CRUD, using disposable services."""
import hashlib
from unittest.mock import AsyncMock

from openapi_spec_validator import validate
import pytest
from redis.exceptions import ConnectionError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from example.shared.models import Job, User, Verification


def test_openapi_is_valid_and_includes_reference_operations(client):
    schema = client.get("/openapi.json").json()
    validate(schema)
    assert "/verification/{verification_id}/document-check" in schema["paths"]
    assert "/customers/export" in schema["paths"]


def test_cache_failure_falls_back_without_changing_permissions(client, customer, auth_headers, monkeypatch):
    cache = client.app.state.cache
    monkeypatch.setattr(cache.redis, "get", AsyncMock(side_effect=ConnectionError("offline")))
    monkeypatch.setattr(cache.redis, "set", AsyncMock(side_effect=ConnectionError("offline")))
    result = client.get("/customers/" + customer["customer_id"], headers=auth_headers)
    assert result.status_code == 200
    assert result.json()["customer_id"] == customer["customer_id"]


def test_commit_failure_rolls_back_verification_and_job(client, customer, auth_headers, monkeypatch):
    original = AsyncSession.commit
    async def fail(session):
        raise SQLAlchemyError("synthetic commit failure")
    monkeypatch.setattr(AsyncSession, "commit", fail)
    result = client.post("/verification/start", headers={**auth_headers, "Idempotency-Key": "rollback"},
                         json={"customer_id": customer["customer_id"]})
    assert result.status_code == 503
    monkeypatch.setattr(AsyncSession, "commit", original)
    async def counts():
        async with client.app.state.sessions() as session:
            return await session.scalar(select(func.count()).select_from(Verification)), await session.scalar(select(func.count()).select_from(Job))
    assert client.portal.call(counts) == (0, 0)
    assert client.app.state.engine.pool.checkedout() == 0


def test_synthetic_upload_is_bounded_and_never_stored(client, customer, auth_headers):
    value = client.post("/verification/start", headers={**auth_headers, "Idempotency-Key": "upload"},
                        json={"customer_id": customer["customer_id"]}).json()
    path = "/verification/" + value["verification_id"] + "/document-check"
    result = client.post(path, headers=auth_headers, files={"document": ("synthetic.txt", b"synthetic", "text/plain")})
    assert result.json() == {"bytes": 9, "sha256": hashlib.sha256(b"synthetic").hexdigest(), "stored": False}
    assert client.post(path, headers=auth_headers, files={"document": ("large.txt", b"x" * (256 * 1024 + 1))}).status_code == 422
    assert client.post(path, headers=auth_headers).status_code == 422


def test_streaming_export_requires_admin_and_releases_read_session(client, customer, identity):
    user, headers = identity
    assert client.get("/customers/export", headers=headers).status_code == 403
    async def promote():
        async with client.app.state.sessions() as session, session.begin():
            (await session.get(User, user["user_id"])).role = "admin"
    client.portal.call(promote)
    result = client.get("/customers/export", headers=headers)
    assert result.status_code == 200
    assert "application/x-ndjson" in result.headers["content-type"]
    assert customer["customer_id"] in result.text
    assert "synthetic@example.com" not in result.text
    assert client.app.state.engine.pool.checkedout() == 0


def test_correlation_rejects_unbounded_values_on_errors(client):
    result = client.get("/auth/me", headers={"X-Correlation-Id": "x" * 1000})
    assert result.status_code == 401
    assert len(result.headers["x-correlation-id"]) == 32


@pytest.mark.parametrize("method,path", [
    ("GET", "/auth/me"), ("GET", "/customers/me"), ("GET", "/customers/recent"),
    ("GET", "/customers/export"), ("GET", "/customers/missing"), ("GET", "/metrics"),
    ("GET", "/verification/missing"), ("POST", "/customers/missing/notification-ticket"),
])
def test_private_operations_require_identity(client, method, path):
    assert client.request(method, path).status_code == 401


def test_readiness_distinguishes_cache_degradation_and_database_failure(client, monkeypatch):
    from contextlib import asynccontextmanager
    redis = client.app.state.redis
    monkeypatch.setattr(redis, "ping", AsyncMock(side_effect=ConnectionError("offline")))
    response = client.get("/health/ready")
    assert response.status_code == 200 and response.json()["cache"] == "degraded"
    @asynccontextmanager
    async def fail():
        raise SQLAlchemyError("offline")
        yield
    class Unavailable:
        connect = staticmethod(fail)
    original = client.app.state.engine
    client.app.state.engine = Unavailable()
    try:
        assert client.get("/health/ready").status_code == 503
        assert client.get("/health/live").status_code == 200
    finally:
        client.app.state.engine = original
