"""Read-only audit reproductions. Run from the repository root with Python >=3.10.

These record current behavior; they are not acceptance tests for desired behavior.
No network servers or external cache services are contacted.
"""
import asyncio
import json
import platform
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import httpx
import msgspec
from starlette.requests import Request
from starlette.testclient import TestClient
from tachyon_api import Body, Depends, Form, Query, Router, Struct, Tachyon
from tachyon_api.background import BackgroundTasks
from tachyon_api.cache import RedisCacheBackend
from tachyon_api.exceptions import HTTPException
from tachyon_api.middlewares.cors import CORSMiddleware
from tachyon_api.processing.compiler import compile_endpoint
from tachyon_api.routing import trie

RESULTS = {}


def scope(path="/", method="GET", headers=None):
    return {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "scheme": "http", "path": path, "raw_path": path.encode(),
            "method": method, "query_string": b"", "headers": headers or [],
            "server": ("test", 80), "client": ("test", 123)}


async def request(app, path="/", method="GET", **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.request(method, path, **kwargs)
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return {"status": response.status_code, "body": body}


async def capture(name, fn):
    try:
        RESULTS[name] = await fn()
    except Exception as exc:
        RESULTS[name] = {"exception": type(exc).__name__, "message": str(exc)}


async def keyword_only():
    app = Tachyon()
    @app.get("/")
    async def endpoint(*, q: int = Query(...)):
        return {"q": q}
    return await request(app, "/?q=3")


async def shifted_default():
    app = Tachyon()
    @app.get("/")
    async def endpoint(x=10, q: int = Query(...)):
        return {"x": x, "q_type": type(q).__name__}
    return await request(app, "/?q=3")


async def path_cache():
    def endpoint(x: int):
        return x
    first = compile_endpoint(endpoint, "/fixed")
    second = compile_endpoint(endpoint, "/{x}")
    return {"same_object": first is second, "path_param_count": second.param_count}


async def request_body():
    app = Tachyon()
    @app.post("/")
    async def endpoint(request: Request, data: dict = Body()):
        return {"body": (await request.body()).decode(), "data": data}
    try:
        return await asyncio.wait_for(request(app, method="POST", json={"x": 1}), .5)
    except asyncio.TimeoutError:
        return {"timeout": True}


async def cors_404():
    app = Tachyon()
    app.add_middleware(CORSMiddleware, allow_origins=["https://a.test"])
    return await request(app, headers={"Origin": "https://a.test"})


async def cors_500():
    app = Tachyon()
    app.add_middleware(CORSMiddleware, allow_origins=["https://a.test", "https://b.test"])
    @app.get("/")
    async def endpoint():
        raise ValueError("audit")
    values = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        for origin in ("https://a.test", "https://b.test", "https://denied.test"):
            response = await client.get("/", headers={"Origin": origin})
            values.append(response.headers.get_list("access-control-allow-origin"))
    return values


async def background_order():
    app = Tachyon()
    events = []
    @app.get("/")
    async def endpoint(bg: BackgroundTasks):
        bg.add_task(lambda: events.append("background"))
        return {"ok": True}
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        events.append(message["type"])
    await app(scope(), receive, send)
    return events


async def chunk_limit():
    app = Tachyon(max_body_size=4)
    @app.post("/")
    async def endpoint(data: dict = Body()):
        return data
    read = 0
    messages = []
    async def receive():
        nonlocal read
        read += 1
        return {"type": "http.request", "body": b"12345", "more_body": read < 5}
    async def send(message):
        messages.append(message)
    await app(scope(method="POST"), receive, send)
    return {"chunks_consumed": read, "status": messages[0]["status"]}


async def form_limit_and_type():
    app = Tachyon(max_body_size=4)
    @app.post("/")
    async def endpoint(n: int = Form(...)):
        return {"type": type(n).__name__, "length": len(n) if isinstance(n, str) else None}
    return await request(app, method="POST", data={"n": "nonsense" * 125})


async def postponed_annotations():
    namespace = {"app": Tachyon(), "Query": Query}
    exec("from __future__ import annotations\n@app.get('/')\nasync def endpoint(q: int = Query(...)):\n    return {'q': q}\n", namespace)
    return await request(namespace["app"], "/?q=3")


async def route_names():
    app = Tachyon()
    @app.get("/names/{id}")
    async def first(id: str):
        return {"id": id}
    @app.post("/names/{name}")
    async def second(name: str):
        return {"name": name}
    return await request(app, "/names/alice", method="POST")


async def route_backtrack():
    app = Tachyon()
    @app.get("/users/{id}/posts")
    async def first(id: str):
        return {"id": id}
    @app.get("/users/admin/settings")
    async def second():
        return {}
    return await request(app, "/users/admin/posts")


async def unicode_route():
    app = Tachyon()
    @app.get("/café/{name}")
    async def endpoint(name: str):
        return {"name": name}
    return await request(app, "/café/niño")


async def ignored_dependencies():
    app = Tachyon()
    calls = []
    async def reject():
        calls.append(True)
        raise HTTPException(401, "denied")
    router = Router(dependencies=[Depends(reject)])
    @router.get("/")
    async def endpoint():
        return {"secret": True}
    app.include_router(router)
    result = await request(app)
    result["dependency_calls"] = len(calls)
    return result


async def payload_mutation():
    class Item(Struct):
        value: int
    shared = {"item": Item(1)}
    app = Tachyon()
    @app.get("/")
    async def endpoint():
        return shared
    result = await request(app)
    result["stored_type_after_response"] = type(shared["item"]).__name__
    return result


async def redis_clear():
    client = MagicMock()
    client.flushdb.side_effect = RuntimeError("database denied")
    RedisCacheBackend(client).clear()
    return {"flushdb_calls": client.flushdb.call_count, "flushall_calls": client.flushall.call_count}


async def lifespan_state():
    @asynccontextmanager
    async def lifespan(app):
        yield {"db": "ready"}
    app = Tachyon(lifespan=lifespan)
    @app.get("/")
    async def endpoint(request: Request):
        return {"db": getattr(request.state, "db", "MISSING")}
    with TestClient(app) as client:
        return client.get("/").json()


async def websocket_di():
    app = Tachyon()
    async def value():
        return "ready"
    @app.websocket("/ws")
    async def endpoint(websocket, injected=Depends(value)):
        await websocket.accept()
        await websocket.send_text(type(injected).__name__)
        await websocket.close()
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            return {"injected_type": websocket.receive_text()}


async def direct_write():
    from tachyon_api.responses import TachyonJSONResponse
    from tachyon_api.server import tachyon_direct_write
    cycle = SimpleNamespace(flow=SimpleNamespace(write_paused=False), disconnected=False,
                            default_headers=[(b"server", b"audit")], transport=MagicMock(),
                            scope={"method": "HEAD"}, keep_alive=True, message_event=asyncio.Event(),
                            on_response=MagicMock())
    response = TachyonJSONResponse({"ok": True})
    response.headers["x-audit"] = "present"
    accepted = tachyon_direct_write(cycle, response)
    wire = b"".join(call.args[0] for call in cycle.transport.write.call_args_list)
    return {"accepted": accepted, "head_has_body": wire.endswith(response.body),
            "custom_header_sent": b"x-audit" in wire, "default_server_header_sent": b"server: audit" in wire}


async def middleware_bypass():
    app = Tachyon()
    app.add_middleware(CORSMiddleware, allow_origins=["https://a.test"])
    @app.get("/")
    async def endpoint():
        return {"ok": True}
    cycle = SimpleNamespace(flow=SimpleNamespace(write_paused=False), disconnected=False,
                            default_headers=[], transport=MagicMock(), scope={"method": "GET"},
                            keep_alive=True, message_event=asyncio.Event(), on_response=MagicMock())
    events = []
    async def receive():
        return {"type": "http.request", "body": b""}
    async def send(message):
        events.append(message)
    request_scope = scope(headers=[(b"origin", b"https://a.test")])
    request_scope["_tachyon_cycle"] = cycle
    await app(request_scope, receive, send)
    wire = b"".join(call.args[0] for call in cycle.transport.write.call_args_list)
    return {"asgi_send_events": len(events), "cors_header_sent": b"access-control-allow-origin" in wire}


async def schema_defaults():
    class Example(Struct):
        required_nullable: int | None
        defaulted: int = 42
    from tachyon_api.openapi._struct_schemas import build_components_for_struct
    return build_components_for_struct(Example)


async def main():
    for fn in (keyword_only, shifted_default, path_cache, request_body, cors_404, cors_500,
               background_order, chunk_limit, form_limit_and_type, postponed_annotations,
               route_names, route_backtrack, unicode_route, ignored_dependencies, payload_mutation,
               redis_clear, lifespan_state, websocket_di, direct_write, middleware_bypass, schema_defaults):
        await capture(fn.__name__, fn)
    print(json.dumps({"environment": {"python": platform.python_version(), "platform": platform.platform(),
                                     "trie_module": trie.__file__, "msgspec": msgspec.__version__},
                      "results": RESULTS}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
