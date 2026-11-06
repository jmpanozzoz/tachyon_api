"""Shared middleware lifetime, docs publication and one body-limit authority."""
from contextlib import asynccontextmanager

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount
from starlette.websockets import WebSocket

from tachyon_api import Body, Tachyon
from tachyon_api.app._route_installer import RouteInstaller
from tachyon_api.openapi import create_openapi_config
from tachyon_api.testing import TachyonTestClient, create_client


def test_middleware_order_identity_and_instances_are_shared_by_all_protocols():
    entries, exits, constructions, lifespan_apps = [], [], [], []

    class Recorder:
        def __init__(self, app, name):
            self.app, self.name = app, name
            constructions.append(self)

        async def __call__(self, scope, receive, send):
            entries.append((scope["type"], self.name, scope["app"]))
            await self.app(scope, receive, send)
            exits.append((scope["type"], self.name, scope["app"]))

    @asynccontextmanager
    async def lifespan(application):
        lifespan_apps.append(application)
        yield {"marker": "ready"}

    app = Tachyon(lifespan=lifespan)
    app.add_middleware(Recorder, name="A")
    app.add_middleware(Recorder, name="B")

    @app.get("/identity")
    async def identity(request: Request):
        assert request.app is app
        return {"marker": request.state.marker}

    @app.websocket("/ws")
    async def socket(websocket: WebSocket):
        assert websocket.app is app
        await websocket.accept()
        await websocket.close()

    assert constructions == []
    with TachyonTestClient(app) as client:
        generation = app._http_app
        assert client.get("/identity").json() == {"marker": "ready"}
        with client.websocket_connect("/ws"):
            pass
        assert app._http_app is generation
    assert lifespan_apps == [app]
    assert [item.name for item in constructions] == ["B", "A"]
    for protocol in ("http", "websocket", "lifespan"):
        assert [name for kind, name, _ in entries if kind == protocol] == ["A", "B"]
        assert [name for kind, name, _ in exits if kind == protocol] == ["B", "A"]
    assert all(application is app for _, _, application in entries + exits)


def test_late_middleware_addition_rebuilds_one_generation_during_lifespan():
    calls, constructions = [], []

    class Recorder:
        def __init__(self, app, name):
            self.app, self.name = app, name
            constructions.append(name)

        async def __call__(self, scope, receive, send):
            calls.append((scope["type"], self.name))
            await self.app(scope, receive, send)

    app = Tachyon()
    app.add_middleware(Recorder, name="A")
    with TachyonTestClient(app) as client:
        old = app._http_app
        assert client.get("/missing").status_code == 404
        app.add_middleware(Recorder, name="B")
        assert app._http_app is None
        assert client.get("/missing").status_code == 404
        assert app._http_app is not old
        assert client.get("/missing").status_code == 404
    assert constructions == ["A", "B", "A"]
    assert [name for kind, name in calls if kind == "http"] == ["A", "A", "B", "A", "B"]


def test_mounted_http_preserves_tachyon_app_identity():
    app = Tachyon()

    @app.get("/identity")
    async def identity(request: Request):
        assert request.app is app
        return {"root": request.scope["root_path"]}

    with TachyonTestClient(Starlette(routes=[Mount("/service", app=app)])) as client:
        assert client.get("/service/identity").json() == {"root": "/service"}


@pytest.mark.asyncio
async def test_failed_middleware_constructor_retries_without_duplicate_docs():
    constructions = []

    class RetryMiddleware:
        def __init__(self, app):
            constructions.append(1)
            if len(constructions) == 1:
                raise RuntimeError("constructor failed")
            self.app = app

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)

    app = Tachyon()
    app.add_middleware(RetryMiddleware)
    async with create_client(app) as client:
        with pytest.raises(RuntimeError, match="constructor failed"):
            await client.get("/docs")
        assert app._http_app is None and len(app.routes) == 4
        assert (await client.get("/docs")).status_code == 200
        assert len(app.routes) == 4 and len(constructions) == 2


def test_replacing_docs_config_fails_clearly_before_registration():
    app = Tachyon()
    original = app.openapi_config
    app.openapi_config = create_openapi_config(title="replacement")
    with pytest.raises(ValueError, match="do not replace"):
        app._docs_routes.setup()
    assert app.routes == [] and not app._docs_routes.setup_done
    app.openapi_config = original
    app._docs_routes.setup()
    assert len(app.routes) == 4


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/swagger", "/openapi.json", "//docs/"])
def test_docs_conflicts_fail_without_partial_registration_and_can_be_retried(path):
    app = Tachyon()

    @app.get(path)
    async def own_docs():
        return {"custom": True}

    routes = list(app.routes)
    with pytest.raises(ValueError, match="conflicts with a documentation route"):
        app._docs_routes.setup()
    assert app.routes == routes
    assert not app._docs_routes.setup_done
    assert app._trie.match(path, "GET")[0] == 2
    # Remove the conflict by moving the corresponding configurable docs URL.
    if "swagger" in path:
        return  # /swagger is fixed: the user route must be renamed instead.
    if "openapi" in path:
        app.openapi_config.openapi_url = "/schema"
    elif "redoc" in path:
        app.openapi_config.redoc_url = "/reference"
    else:
        app.openapi_config.docs_url = "/reference"
    app._docs_routes.setup()
    assert len(app.routes) == len(routes) + 4


def test_docs_prepares_every_endpoint_before_publishing(monkeypatch):
    app = Tachyon()
    original = RouteInstaller.prepare
    calls = []

    def fail_third(installer, path, endpoint, **kwargs):
        calls.append(path)
        if len(calls) == 3:
            raise TypeError("cannot prepare docs endpoint")
        return original(installer, path, endpoint, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(RouteInstaller, "prepare", fail_third)
        with pytest.raises(TypeError, match="cannot prepare"):
            app._docs_routes.setup()
    assert app.routes == []
    assert not app._docs_routes.setup_done
    assert app._trie.match("/docs", "GET")[0] == 0
    app._docs_routes.setup()
    assert len(app.routes) == 4


@pytest.mark.parametrize("invalid", ["/swagger", "//swagger/", "relative", "/{name}", "/docs?x", None])
def test_invalid_or_duplicate_docs_paths_leave_no_partial_state(invalid):
    app = Tachyon()
    app.openapi_config.docs_url = invalid
    with pytest.raises(ValueError):
        app._docs_routes.setup()
    assert app.routes == []
    assert not app._docs_routes.setup_done


@pytest.mark.asyncio
async def test_docs_paths_are_bound_once_and_cannot_be_overwritten_after_setup():
    app = Tachyon()
    app.openapi_config.docs_url = "/reference"
    app.openapi_config.openapi_url = "/schema"
    async with create_client(app) as client:
        response = await client.get("/reference")
        assert response.status_code == 200 and "/schema" in response.text
        assert len(app.routes) == 4
        with pytest.raises(ValueError, match="conflicts"):
            app.get("//reference/")(lambda: {})
        assert len(app.routes) == 4
        app.openapi_config.openapi_url = "/changed-after-setup"
        assert "/schema" in (await client.get("/reference")).text
        assert (await client.get("/schema")).status_code == 200
        assert (await client.get("/changed-after-setup")).status_code == 404


@pytest.mark.asyncio
async def test_external_schema_url_is_rendered_without_registering_a_local_url():
    app = Tachyon(openapi_config=create_openapi_config(openapi_url="https://schemas.example/api.json"))
    async with create_client(app) as client:
        assert "https://schemas.example/api.json" in (await client.get("/docs")).text
    assert len(app.routes) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("initial,updated,expected", [(1, 100, 200), (100, 1, 422)])
async def test_json_body_uses_the_same_current_limit_as_request_reads(initial, updated, expected):
    app = Tachyon(max_body_size=initial)

    @app.post("/body")
    async def endpoint(body: dict = Body()):
        return body

    @app.post("/request")
    async def request_endpoint(request: Request):
        return await request.json()

    app.max_body_size = updated
    async with create_client(app) as client:
        for path in ("/body", "/request"):
            response = await client.post(path, json={"value": 1})
            assert response.status_code == expected
            if expected == 422:
                assert response.headers["connection"] == "close"
