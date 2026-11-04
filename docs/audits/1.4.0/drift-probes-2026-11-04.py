"""Document/code discrepancy reproductions; no runtime source edits."""
import asyncio
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import httpx
from starlette.requests import Request
from starlette.testclient import TestClient
from tachyon_api import Body, Depends, File, Header, Path as PathParam, Query, Struct, Tachyon, injectable
from tachyon_api.background import BackgroundTasks
from tachyon_api.files import UploadFile
from tachyon_api.processing.dependencies._resolver import DependencyResolver
from tachyon_api.routing import trie
from tachyon_api.cache import InMemoryCacheBackend, CacheConfig, cache


async def fetch(app, method="GET", path="/", **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.request(method, path, **kwargs)
    try:
        data = response.json()
    except ValueError:
        data = response.text
    return {"status": response.status_code, "body": data}


async def main():
    results = {}
    try:
        PathParam(..., description="ID")
    except Exception as exc:
        results["documented_path_constructor"] = {"type": type(exc).__name__, "message": str(exc)}
    try:
        Query(..., alias="query")
    except Exception as exc:
        results["documented_query_alias"] = {"type": type(exc).__name__, "message": str(exc)}
    class Mutable(Struct):
        value: int
    model = Mutable(1)
    model.value = 2
    results["struct_mutable"] = model.value
    try:
        dict(model.__dict__)
    except Exception as exc:
        results["documented_struct_dict"] = type(exc).__name__
    app = Tachyon()
    @app.get("/")
    async def invalid_response():
        return Mutable("wrong")
    # A declared response model still trusts an existing same-type Struct.
    other = Tachyon()
    other.get("/", response_model=Mutable)(invalid_response)
    results["response_model_same_struct_type"] = await fetch(other)

    app = Tachyon()
    def auth(token: str = Header(...)):
        return token.startswith("Bearer ")
    @app.get("/")
    async def dependency(value=Depends(auth)):
        return {"value": value}
    results["header_inside_dependency"] = await fetch(app, headers={"token": "Bearer allowed"})

    @injectable(scope="request")
    class Context:
        def __init__(self, request: Request):
            self.user = request.headers["x-user"]
    @injectable
    class Service:
        def __init__(self, context: Context):
            self.context = context
    app = Tachyon()
    @app.get("/")
    async def captive(service: Service, context: Context):
        return {"service_user": service.context.user, "request_user": context.user,
                "same_context": service.context is context}
    results["singleton_request_scope"] = [await fetch(app, headers={"x-user": name}) for name in ("alice", "bob")]

    app = Tachyon()
    @app.post("/")
    async def filename(file: UploadFile = File(...)):
        return {"filename": file.filename, "actual_type": type(file).__module__ + "." + type(file).__name__,
                "tachyon_uploadfile": isinstance(file, UploadFile)}
    results["filename_sanitization"] = await fetch(app, "POST", files={"file": ("../../sensitive.txt", b"demo")})

    app = Tachyon()
    @app.post("/")
    async def gallery(images: list[UploadFile] = File(...)):
        return {"files": [image.filename for image in images]}
    results["multiple_files"] = await fetch(app, "POST", files=[("images", ("a.txt", b"a")), ("images", ("b.txt", b"b"))])

    app = Tachyon()
    @app.get("/{day}")
    async def date_path(day: datetime.date):
        return {"day": day.isoformat()}
    results["date_path"] = await fetch(app, path="/2026-11-04")

    app = Tachyon()
    effects = []
    @app.get("/")
    async def optional_background(bg: BackgroundTasks = None):
        if bg:
            bg.add_task(effects.append, "ran")
        return {"ok": True}
    await fetch(app)
    results["optional_background_example_tasks"] = effects

    config = CacheConfig(InMemoryCacheBackend())
    def make(value):
        @cache(config=config)
        def cached():
            return value
        return cached
    first, second = make("a"), make("b")
    results["cache_function_identity"] = {"first": first(), "second": second()}
    try:
        @cache(ttl=300)
        def invalid_cache():
            return 1
    except Exception as exc:
        results["documented_lowercase_ttl"] = type(exc).__name__

    def untyped_websocket(websocket):
        return websocket.query_params.get("token")
    app = Tachyon()
    from starlette.websockets import WebSocket
    @app.websocket("/ws")
    async def ws(websocket: WebSocket, user=Depends(untyped_websocket)):
        await websocket.accept()
        await websocket.send_json({"user": user})
    try:
        with TestClient(app) as client:
            with client.websocket_connect("/ws?token=demo") as connection:
                results["untyped_ws_dependency"] = connection.receive_json()
    except Exception as exc:
        results["untyped_ws_dependency"] = {"type": type(exc).__name__, "message": str(exc)}
    print(json.dumps({"python": sys.version, "engine": trie.__file__, "results": results}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
