import pytest
from httpx import AsyncClient, ASGITransport

from tachyon_api import Tachyon
from tachyon_api.middlewares import CORSMiddleware


@pytest.mark.asyncio
async def test_cors_preflight_allows_any_origin_no_credentials():
    app = Tachyon()

    # Add CORS with wildcard origin and no credentials
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        allow_credentials=False,
        max_age=600,
    )

    # Dummy route (won't be hit on preflight)
    @app.get("/preflight")
    def preflight_target():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Token",
        }
        response = await client.options("/preflight", headers=headers)

    assert response.status_code == 200
    # Wildcard origin allowed when no credentials
    assert response.headers.get("access-control-allow-origin") == "*"
    # Methods reflect configured methods
    assert response.headers.get("access-control-allow-methods") in (
        "GET, POST",
        "GET, POST",
    )
    # With allow_headers='*', it should echo requested headers
    assert response.headers.get("access-control-allow-headers") == "X-Token"
    # Max age included
    assert response.headers.get("access-control-max-age") == "600"
    # Should not include Vary when wildcard origin + no credentials
    assert response.headers.get("vary") is None


@pytest.mark.asyncio
async def test_cors_preflight_echo_origin_with_credentials():
    app = Tachyon()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://example.com"],
        allow_methods=["*"],
        allow_headers=["content-type"],
        allow_credentials=True,
        max_age=120,
    )

    @app.get("/preflight-creds")
    def target():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers = {
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
        }
        response = await client.options("/preflight-creds", headers=headers)

    assert response.status_code == 200
    # Echo origin and include Vary when credentials are allowed
    assert response.headers.get("access-control-allow-origin") == "http://example.com"
    assert response.headers.get("vary") == "Origin"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_normal_request_injects_headers():
    app = Tachyon()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://example.com"],
        allow_methods=["GET"],
        allow_headers=["*"],
        allow_credentials=False,
        expose_headers=["X-Total-Count"],
    )

    @app.get("/items")
    def items():
        return {"items": []}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/items", headers={"Origin": "http://example.com"})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in (
        "http://example.com",
        "*",
    )
    # Expose headers should be present
    assert response.headers.get("access-control-expose-headers") == "X-Total-Count"
