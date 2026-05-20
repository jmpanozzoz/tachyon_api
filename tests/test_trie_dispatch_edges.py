"""
HF-10 + HF-11: Edge cases in trie dispatch and middleware execution after bypass.
"""

import pytest
from starlette.testclient import TestClient
from tests.helpers import create_client
from tachyon_api import Tachyon
from tachyon_api.middlewares import CORSMiddleware


# ── Trie dispatch edge cases (HF-10) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_404_nonexistent_path():
    app = Tachyon()

    @app.get("/exists")
    def ep():
        return {}

    async with create_client(app) as client:
        r = await client.get("/nope")

    assert r.status_code == 404


@pytest.mark.asyncio
async def test_trailing_slash_treated_as_equivalent():
    # Trie filters empty path segments — /users/ and /users resolve identically.
    app = Tachyon()

    @app.get("/users")
    def ep():
        return {"ok": True}

    async with create_client(app) as client:
        r = await client.get("/users/")

    assert r.status_code == 200  # trailing slash handled transparently


@pytest.mark.asyncio
async def test_path_case_sensitive():
    app = Tachyon()

    @app.get("/Users")
    def ep():
        return {"case": "upper"}

    async with create_client(app) as client:
        r1 = await client.get("/Users")
        r2 = await client.get("/users")

    assert r1.status_code == 200
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_root_path_matched():
    app = Tachyon()

    @app.get("/")
    def root():
        return {"root": True}

    async with create_client(app) as client:
        r = await client.get("/")

    assert r.status_code == 200
    assert r.json() == {"root": True}


@pytest.mark.asyncio
async def test_websocket_unaffected_by_http_bypass():
    """HF-10: WebSocket routing must still work after Phase 4 HTTP bypass."""
    app = Tachyon()

    @app.get("/http")
    def http_ep():
        return {"type": "http"}

    @app.websocket("/ws")
    async def ws_ep(websocket):
        await websocket.accept()
        await websocket.send_json({"type": "websocket"})
        await websocket.close()

    client = TestClient(app)

    http_resp = client.get("/http")
    assert http_resp.status_code == 200
    assert http_resp.json() == {"type": "http"}

    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg == {"type": "websocket"}


# ── Middleware execution after bypass (HF-11) ──────────────────────────────────

@pytest.mark.asyncio
async def test_user_middleware_executes_around_trie_dispatch():
    """Phase 4 bypasses Starlette's error middlewares but NOT user middlewares."""
    app = Tachyon()
    call_order = []

    class TrackingMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                call_order.append("before")
                await self.app(scope, receive, send)
                call_order.append("after")
            else:
                await self.app(scope, receive, send)

    app.add_middleware(TrackingMiddleware)

    @app.get("/test")
    def ep():
        call_order.append("handler")
        return {}

    async with create_client(app) as client:
        await client.get("/test")

    assert call_order == ["before", "handler", "after"]


@pytest.mark.asyncio
async def test_cors_middleware_works_after_bypass():
    """CORS middleware must still apply headers after Phase 4 bypass."""
    app = Tachyon()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://example.com"],
        allow_methods=["GET"],
    )

    @app.get("/data")
    def ep():
        return {"ok": True}

    async with create_client(app) as client:
        r = await client.get("/data", headers={"Origin": "http://example.com"})

    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://example.com"


@pytest.mark.asyncio
async def test_middleware_added_before_first_request_is_applied():
    """Middleware added before first request must be included in _http_app."""
    app = Tachyon()
    hit = []

    class Marker:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                hit.append(1)
            await self.app(scope, receive, send)

    app.add_middleware(Marker)

    @app.get("/x")
    def ep():
        return {}

    assert app._http_app is None  # not built yet

    async with create_client(app) as client:
        await client.get("/x")

    assert len(hit) == 1
    assert app._http_app is not None


@pytest.mark.asyncio
async def test_middleware_added_after_first_request_triggers_rebuild():
    """Adding middleware after first request invalidates _http_app cache."""
    app = Tachyon()

    @app.get("/x")
    def ep():
        return {}

    async with create_client(app) as client:
        await client.get("/x")
        first_app = app._http_app

        class Noop:
            def __init__(self, app):
                self.app = app
            async def __call__(self, scope, receive, send):
                await self.app(scope, receive, send)

        app.add_middleware(Noop)
        assert app._http_app is None  # invalidated

        await client.get("/x")
        second_app = app._http_app

    assert first_app is not second_app
