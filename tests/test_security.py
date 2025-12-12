"""
Tests for Security schemes (TDD).
Release 0.6.4 - Security Foundation
"""

import pytest
from httpx import AsyncClient, ASGITransport


# =============================================================================
# HTTPBearer Tests
# =============================================================================

@pytest.mark.asyncio
async def test_http_bearer_valid_token():
    """HTTPBearer should extract Bearer token from Authorization header."""
    from tachyon_api import Tachyon, Depends, HTTPException
    from tachyon_api.security import HTTPBearer, HTTPAuthorizationCredentials

    app = Tachyon()
    security = HTTPBearer()

    @app.get("/protected")
    def protected(credentials: HTTPAuthorizationCredentials = Depends(security)):
        return {"token": credentials.credentials, "scheme": credentials.scheme}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": "Bearer my-secret-token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "my-secret-token"
        assert data["scheme"] == "Bearer"


@pytest.mark.asyncio
async def test_http_bearer_missing_header():
    """HTTPBearer should return 403 when Authorization header is missing."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import HTTPBearer, HTTPAuthorizationCredentials

    app = Tachyon()
    security = HTTPBearer()

    @app.get("/protected")
    def protected(credentials: HTTPAuthorizationCredentials = Depends(security)):
        return {"token": credentials.credentials}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/protected")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_http_bearer_invalid_scheme():
    """HTTPBearer should return 403 when scheme is not Bearer."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import HTTPBearer, HTTPAuthorizationCredentials

    app = Tachyon()
    security = HTTPBearer()

    @app.get("/protected")
    def protected(credentials: HTTPAuthorizationCredentials = Depends(security)):
        return {"token": credentials.credentials}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_http_bearer_auto_error_false():
    """HTTPBearer with auto_error=False should return None on missing token."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import HTTPBearer, HTTPAuthorizationCredentials
    from typing import Optional

    app = Tachyon()
    security = HTTPBearer(auto_error=False)

    @app.get("/optional")
    def optional_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
        if credentials is None:
            return {"authenticated": False}
        return {"authenticated": True, "token": credentials.credentials}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Without token
        response = await client.get("/optional")
        assert response.status_code == 200
        assert response.json() == {"authenticated": False}

        # With token
        response = await client.get(
            "/optional",
            headers={"Authorization": "Bearer valid-token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["token"] == "valid-token"


# =============================================================================
# HTTPBasic Tests
# =============================================================================

@pytest.mark.asyncio
async def test_http_basic_valid_credentials():
    """HTTPBasic should extract username and password."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import HTTPBasic, HTTPBasicCredentials
    import base64

    app = Tachyon()
    security = HTTPBasic()

    @app.get("/basic")
    def basic_auth(credentials: HTTPBasicCredentials = Depends(security)):
        return {"username": credentials.username, "password": credentials.password}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Encode "admin:secret123"
        encoded = base64.b64encode(b"admin:secret123").decode()
        response = await client.get(
            "/basic",
            headers={"Authorization": f"Basic {encoded}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["password"] == "secret123"


@pytest.mark.asyncio
async def test_http_basic_missing_header():
    """HTTPBasic should return 401 when missing."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import HTTPBasic, HTTPBasicCredentials

    app = Tachyon()
    security = HTTPBasic()

    @app.get("/basic")
    def basic_auth(credentials: HTTPBasicCredentials = Depends(security)):
        return {"username": credentials.username}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/basic")
        assert response.status_code == 401
        # Should include WWW-Authenticate header
        assert "WWW-Authenticate" in response.headers


# =============================================================================
# APIKey Tests
# =============================================================================

@pytest.mark.asyncio
async def test_api_key_header():
    """APIKeyHeader should extract API key from header."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import APIKeyHeader

    app = Tachyon()
    api_key_header = APIKeyHeader(name="X-API-Key")

    @app.get("/api")
    def api_endpoint(api_key: str = Depends(api_key_header)):
        return {"api_key": api_key}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api",
            headers={"X-API-Key": "my-api-key-123"}
        )
        assert response.status_code == 200
        assert response.json() == {"api_key": "my-api-key-123"}


@pytest.mark.asyncio
async def test_api_key_header_missing():
    """APIKeyHeader should return 403 when missing."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import APIKeyHeader

    app = Tachyon()
    api_key_header = APIKeyHeader(name="X-API-Key")

    @app.get("/api")
    def api_endpoint(api_key: str = Depends(api_key_header)):
        return {"api_key": api_key}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_key_query():
    """APIKeyQuery should extract API key from query parameter."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import APIKeyQuery

    app = Tachyon()
    api_key_query = APIKeyQuery(name="api_key")

    @app.get("/api")
    def api_endpoint(api_key: str = Depends(api_key_query)):
        return {"api_key": api_key}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api?api_key=query-key-456")
        assert response.status_code == 200
        assert response.json() == {"api_key": "query-key-456"}


@pytest.mark.asyncio
async def test_api_key_cookie():
    """APIKeyCookie should extract API key from cookie."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import APIKeyCookie

    app = Tachyon()
    api_key_cookie = APIKeyCookie(name="session_token")

    @app.get("/api")
    def api_endpoint(api_key: str = Depends(api_key_cookie)):
        return {"api_key": api_key}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api",
            cookies={"session_token": "cookie-key-789"}
        )
        assert response.status_code == 200
        assert response.json() == {"api_key": "cookie-key-789"}


# =============================================================================
# OAuth2PasswordBearer Tests
# =============================================================================

@pytest.mark.asyncio
async def test_oauth2_password_bearer():
    """OAuth2PasswordBearer should extract token from Authorization header."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import OAuth2PasswordBearer

    app = Tachyon()
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

    @app.get("/users/me")
    def get_current_user(token: str = Depends(oauth2_scheme)):
        return {"token": token}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/users/me",
            headers={"Authorization": "Bearer jwt-token-here"}
        )
        assert response.status_code == 200
        assert response.json() == {"token": "jwt-token-here"}


@pytest.mark.asyncio
async def test_oauth2_password_bearer_missing():
    """OAuth2PasswordBearer should return 401 when missing."""
    from tachyon_api import Tachyon, Depends
    from tachyon_api.security import OAuth2PasswordBearer

    app = Tachyon()
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

    @app.get("/users/me")
    def get_current_user(token: str = Depends(oauth2_scheme)):
        return {"token": token}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/users/me")
        assert response.status_code == 401
