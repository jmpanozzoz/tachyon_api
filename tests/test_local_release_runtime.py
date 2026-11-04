"""Additional local release regressions for ASGI routing boundaries."""

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from tachyon_api import Tachyon, Query, Header, Body, Form, File, Cookie


@pytest.mark.asyncio
async def test_http_routes_work_when_mounted_beneath_root_path():
    child = Tachyon()

    @child.get("/items/{item_id}")
    async def endpoint(item_id: int):
        return {"item_id": item_id}

    parent = Starlette(routes=[Mount("/api", app=child)])
    async with AsyncClient(transport=ASGITransport(app=parent), base_url="http://testserver") as client:
        response = await client.get("/api/items/7")
    assert response.status_code == 200
    assert response.json() == {"item_id": 7}


def test_websocket_routes_work_when_mounted_beneath_root_path():
    child = Tachyon()

    @child.websocket("/items/{item_id}")
    async def endpoint(websocket, item_id: int):
        await websocket.accept()
        await websocket.send_json({"item_id": item_id})
        await websocket.close()

    parent = Starlette(routes=[Mount("/api", app=child)])
    with TestClient(parent) as client:
        with client.websocket_connect("/api/items/7") as websocket:
            assert websocket.receive_json() == {"item_id": 7}


@pytest.mark.parametrize("marker", [Query(...), Header(...), Body(), Form(...), File(...), Cookie(...)])
def test_unsupported_websocket_endpoint_markers_fail_at_registration(marker):
    async def endpoint(websocket, value: str = marker):
        await websocket.accept()
        await websocket.send_text(value)

    with pytest.raises(TypeError, match="[Mm]arker|[Pp]arameter|supported"):
        Tachyon().websocket("/socket")(endpoint)


@pytest.mark.asyncio
async def test_dynamic_mount_parameters_are_preserved_with_decoded_unicode_paths():
    from starlette.requests import Request

    child = Tachyon()

    @child.get("/items/{item_id}")
    async def endpoint(request: Request, item_id: str):
        return {"params": request.path_params, "item_id": item_id, "path": request.url.path}

    parent = Starlette(routes=[Mount("/café/{tenant}", app=child)])
    async with AsyncClient(transport=ASGITransport(app=parent), base_url="http://testserver") as client:
        response = await client.get("/caf%C3%A9/alice/items/%CE%BB")
    assert response.status_code == 200
    assert response.json() == {
        "params": {"tenant": "alice", "item_id": "λ"},
        "item_id": "λ",
        "path": "/café/alice/items/λ",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("root_path,path,expected", [
    ("/api", "/api/items/7", 200),
    ("/api", "/items/7", 200),
    ("/api", "/apix/items/7", 404),
    ("/api", "/other/api/items/7", 404),
    ("/", "/items/7", 200),
])
async def test_root_path_removal_obeys_component_boundaries(root_path, path, expected):
    child = Tachyon()

    @child.get("/items/{item_id}")
    async def endpoint(item_id: int):
        return {"item_id": item_id}

    transport = ASGITransport(app=child, root_path=root_path)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(path)
    assert response.status_code == expected


@pytest.mark.parametrize("docs_path", ["/docs", "/swagger", "/redoc"])
@pytest.mark.parametrize("configured_url,expected_url", [
    ("/openapi.json", "/api/openapi.json"),
    ("schemas/openapi.json", "/api/schemas/openapi.json"),
    ("/custom/schema.json", "/api/custom/schema.json"),
    ("https://specs.example/openapi.json", "https://specs.example/openapi.json"),
    ("//specs.example/openapi.json", "//specs.example/openapi.json"),
])
@pytest.mark.asyncio
async def test_mounted_documentation_schema_urls(docs_path, configured_url, expected_url):
    from tachyon_api.openapi import OpenAPIConfig

    child = Tachyon(openapi_config=OpenAPIConfig(openapi_url=configured_url))
    parent = Starlette(routes=[Mount("/api", app=child)])
    async with AsyncClient(transport=ASGITransport(app=parent), base_url="http://testserver") as client:
        response = await client.get("/api" + docs_path)
        assert response.status_code == 200
        assert expected_url in response.text
        if not configured_url.startswith(("https://", "//")):
            assert (await client.get(expected_url)).status_code == 200


@pytest.mark.asyncio
async def test_documentation_root_path_is_request_owned_for_dynamic_mounts():
    child = Tachyon()
    parent = Starlette(routes=[Mount("/tenants/{tenant}", app=child)])
    async with AsyncClient(transport=ASGITransport(app=parent), base_url="http://testserver") as client:
        for tenant in ("alice", "bob"):
            response = await client.get(f"/tenants/{tenant}/docs")
            assert f"/tenants/{tenant}/openapi.json" in response.text


@pytest.mark.asyncio
async def test_mounted_schema_server_overlay_is_isolated_per_request():
    child = Tachyon()
    parent = Starlette(routes=[Mount("/tenants/{tenant}", app=child)])
    async with AsyncClient(transport=ASGITransport(app=parent), base_url="http://testserver") as client:
        for tenant in ("alice", "bob"):
            schema = (await client.get(f"/tenants/{tenant}/openapi.json")).json()
            assert schema["servers"] == [{"url": f"/tenants/{tenant}"}]
            assert "servers" not in child.openapi_generator.get_openapi_schema()
    async with AsyncClient(transport=ASGITransport(app=child), base_url="http://testserver") as client:
        assert "servers" not in (await client.get("/openapi.json")).json()


@pytest.mark.asyncio
async def test_mounted_schema_preserves_explicit_servers():
    from tachyon_api.openapi import OpenAPIConfig, Server

    expected = [{"url": "https://api.example/v2", "description": "Explicit API"}]
    child = Tachyon(openapi_config=OpenAPIConfig(servers=[Server(**expected[0])]))
    parent = Starlette(routes=[Mount("/api", app=child)])
    async with AsyncClient(transport=ASGITransport(app=parent), base_url="http://testserver") as client:
        schema = (await client.get("/api/openapi.json")).json()
    assert schema["servers"] == expected
    assert child.openapi_generator.get_openapi_schema()["servers"] == expected
