"""Authentication uses real persistence, hashing and current database identity."""
from datetime import timedelta
import jwt
import pytest
from example.shared.models import User, now
from .conftest import register


def test_registration_login_and_current_identity(client, identity):
    user, headers = identity
    assert client.get("/auth/me", headers=headers).json() == user
    async def encoded():
        async with client.app.state.sessions() as session:
            return (await session.get(User, user["user_id"])).password_hash
    value = client.portal.call(encoded)
    assert value.startswith("$argon2id$") and "synthetic-password" not in value


@pytest.mark.parametrize("body,status", [
    ({"email": "missing@example.com", "password": "wrong"}, 401),
    ({"email": "alice@example.com", "password": "wrong"}, 401),
    ({"email": "alice@example.com"}, 422),
])
def test_login_failures(client, identity, body, status):
    assert client.post("/auth/login", json=body).status_code == status


@pytest.mark.parametrize("claim", ["expired", "sub", "iat", "iss", "aud", "signature"])
def test_invalid_tokens(client, identity, claim):
    user, _ = identity
    settings = client.app.state.settings
    payload = {"sub": user["user_id"], "iat": now(), "exp": now() + timedelta(hours=1),
               "iss": settings.jwt_issuer, "aud": settings.jwt_audience}
    if claim == "expired":
        payload["exp"] = now() - timedelta(seconds=1)
    elif claim != "signature":
        del payload[claim]
    token = jwt.encode(payload, "wrong-signature-key-with-32-characters" if claim == "signature" else settings.secret_key, algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_disabled_user_is_rejected_with_previously_valid_token(client, identity):
    user, headers = identity
    async def disable():
        async with client.app.state.sessions() as session, session.begin():
            (await session.get(User, user["user_id"])).active = False
    client.portal.call(disable)
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post("/auth/login", json={"email": user["email"], "password": "synthetic-password"}).status_code == 401


def test_roles_come_from_database_and_unauthenticated_access_fails(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/metrics").status_code == 401
    user, headers = register(client)
    assert client.get("/metrics", headers=headers).status_code == 403
    async def promote():
        async with client.app.state.sessions() as session, session.begin():
            (await session.get(User, user["user_id"])).role = "admin"
    client.portal.call(promote)
    assert client.get("/metrics", headers=headers).status_code == 200


def test_registration_conflict_and_password_policy(client, identity):
    assert client.post("/auth/register", json={"email": "alice@example.com", "password": "synthetic-password", "full_name": "Alice"}).status_code == 409
    assert client.post("/auth/register", json={"email": "short@example.com", "password": "short", "full_name": "Alice"}).status_code == 422


def test_login_limit_is_shared_persistently(client, identity):
    for _ in range(client.app.state.settings.login_limit):
        response = client.post("/auth/login", json={"email": "alice@example.com", "password": "wrong"})
    assert response.status_code == 429
