"""
Async integration tests using `tachyon_api.testing.create_client`.

Shows the modern pattern for testing Tachyon apps end-to-end with httpx
under an ASGI transport — no real network, full ASGI lifecycle exercised.

Run with:
    pytest example/tests/test_async_client.py -v
"""

import jwt
import pytest

from tachyon_api.testing import create_client

from ..app import app
from ..config import settings


def _auth_headers() -> dict:
    """Build a Bearer Authorization header with a valid JWT."""
    from datetime import datetime, timedelta

    token = jwt.encode(
        {
            "sub": "async_test_user",
            "email": "async@example.com",
            "role": "user",
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow(),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health_endpoint_async():
    """Smoke test — the root health endpoint responds 200 with valid JSON."""
    async with create_client(app) as client:
        response = await client.get("/")
        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "healthy"
        assert body["version"] == "1.2.0"


@pytest.mark.asyncio
async def test_security_headers_present():
    """SecurityHeadersMiddleware adds opt-in protections on every response."""
    async with create_client(app) as client:
        response = await client.get("/health")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_create_client_forwards_default_headers():
    """create_client accepts httpx kwargs — verify headers reach the app."""
    headers = {"X-Trace-Id": "abc-123"}
    async with create_client(app, headers=headers) as client:
        # The header is forwarded by the test client even though no endpoint
        # echoes it; this confirms `create_client` accepts httpx options.
        response = await client.get("/")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_http_exception_handler_routes_kyc_exception():
    """
    Unauthenticated GET /customers/me raises `UnauthorizedError(KYCException)`
    which is an HTTPException — the `@app.exception_handler(HTTPException)`
    branch dispatches by isinstance and emits the `UNAUTHORIZED` code.
    """
    async with create_client(app) as client:
        response = await client.get("/customers/me")
        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_recent_customers_returns_list_struct():
    """
    `GET /customers/recent` declares `response_model=List[CustomerResponse]`.
    Whether the list is empty (clean test DB) or not, the response body must
    be a JSON array — not a wrapper object.
    """
    async with create_client(app) as client:
        response = await client.get(
            "/customers/recent?limit=3",
            headers=_auth_headers(),
        )
        assert response.status_code == 200
        body = response.json()
        # response_model=List[CustomerResponse] always produces an array
        assert isinstance(body, list)
