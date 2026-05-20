"""
HF-07: Tests for the _ASGIHandler fast path.

Endpoints with no params and no callable deps are registered as _ASGIHandler
objects that call the handler with (scope, receive, send) directly, skipping
Request() object creation.
"""

import pytest
from starlette.responses import JSONResponse
from tests.helpers import create_client
from tachyon_api import Tachyon, Struct, Body
from tachyon_api.exceptions import HTTPException


@pytest.mark.asyncio
async def test_no_param_endpoint_returns_correct_response():
    app = Tachyon()

    @app.get("/simple")
    def simple():
        return {"ok": True}

    async with create_client(app) as client:
        r = await client.get("/simple")

    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_no_param_async_endpoint_works():
    app = Tachyon()

    @app.get("/async")
    async def async_ep():
        return {"async": True}

    async with create_client(app) as client:
        r = await client.get("/async")

    assert r.status_code == 200
    assert r.json() == {"async": True}


@pytest.mark.asyncio
async def test_fastpath_http_exception_returns_correct_status():
    app = Tachyon()

    @app.get("/forbidden")
    def forbidden():
        raise HTTPException(status_code=403, detail="Forbidden")

    async with create_client(app) as client:
        r = await client.get("/forbidden")

    assert r.status_code == 403
    assert r.json()["detail"] == "Forbidden"


@pytest.mark.asyncio
async def test_fastpath_http_exception_with_headers():
    app = Tachyon()

    @app.get("/auth-required")
    def auth_required():
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with create_client(app) as client:
        r = await client.get("/auth-required")

    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_fastpath_custom_exception_handler_invoked():
    app = Tachyon()

    class DomainError(Exception):
        pass

    @app.exception_handler(DomainError)
    async def handle_domain(request, exc):
        return JSONResponse({"domain": str(exc)}, status_code=422)

    @app.get("/domain-error")
    def raise_domain():
        raise DomainError("bad input")

    async with create_client(app) as client:
        r = await client.get("/domain-error")

    assert r.status_code == 422
    assert r.json()["domain"] == "bad input"


@pytest.mark.asyncio
async def test_fastpath_unhandled_exception_returns_500():
    app = Tachyon()

    @app.get("/crash")
    def crash():
        raise ValueError("unexpected")

    async with create_client(app) as client:
        r = await client.get("/crash")

    assert r.status_code == 500


@pytest.mark.asyncio
async def test_endpoint_with_params_does_not_use_fastpath():
    """Endpoint with Query param should NOT be an _ASGIHandler — it has params."""
    from tachyon_api import Query
    app = Tachyon()

    @app.get("/search")
    def search(q: str = Query(...)):
        return {"q": q}

    async with create_client(app) as client:
        r = await client.get("/search?q=hello")

    assert r.status_code == 200
    assert r.json()["q"] == "hello"


@pytest.mark.asyncio
async def test_multiple_fastpath_endpoints_isolated():
    """Multiple no-param endpoints don't interfere with each other."""
    app = Tachyon()

    @app.get("/a")
    def ep_a():
        return {"endpoint": "a"}

    @app.get("/b")
    def ep_b():
        return {"endpoint": "b"}

    @app.get("/c")
    def ep_c():
        return {"endpoint": "c"}

    async with create_client(app) as client:
        ra = await client.get("/a")
        rb = await client.get("/b")
        rc = await client.get("/c")

    assert ra.json() == {"endpoint": "a"}
    assert rb.json() == {"endpoint": "b"}
    assert rc.json() == {"endpoint": "c"}
