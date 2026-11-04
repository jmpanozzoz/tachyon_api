"""Regression contracts for request ownership, authorization, and execution."""
import asyncio
import threading
from contextlib import asynccontextmanager

import pytest
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from tachyon_api import Body, Depends, File, Form, HTTPException, Query, Router, Struct, Tachyon
from tachyon_api.background import BackgroundTasks
from tachyon_api.middlewares.cors import CORSMiddleware
from tachyon_api.responses import TachyonJSONResponse
from tests.helpers import create_client


def scope(path="/", method="GET", headers=()):
    return {"type": "http", "http_version": "1.1", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "scheme": "http", "path": path, "raw_path": path.encode(), "method": method,
            "query_string": b"", "headers": list(headers), "server": ("test", 80), "client": ("test", 123)}


@pytest.mark.asyncio
async def test_router_and_endpoint_dependencies_share_request_cache():
    calls = []
    async def authorize():
        calls.append(True)
        return "authorized"
    router = Router(prefix="/users", dependencies=[Depends(authorize)])
    @router.get("/")
    async def endpoint(auth=Depends(authorize)):
        return {"auth": auth}
    app = Tachyon()
    app.include_router(router, prefix="/v1", dependencies=[Depends(authorize)])
    async with create_client(app) as client:
        for _ in range(2):
            response = await client.get("/v1/users")
            assert response.status_code == 200
            assert response.json() == {"auth": "authorized"}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_router_authorization_prevents_endpoint_execution():
    reached = []
    async def deny():
        raise HTTPException(401, "denied")
    router = Router(dependencies=[Depends(deny)])
    @router.get("/")
    async def endpoint():
        reached.append(True)
        return {"secret": True}
    app = Tachyon()
    app.include_router(router)
    async with create_client(app) as client:
        response = await client.get("/")
    assert response.status_code == 401
    assert not reached


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 500])
async def test_cors_error_headers_do_not_leak_between_requests_or_apps(status):
    for _ in range(2):
        app = Tachyon()
        app.add_middleware(CORSMiddleware, allow_origins=["https://a.test", "https://b.test"])
        if status == 500:
            @app.get("/")
            async def crash():
                raise ValueError("expected test failure")
        async with create_client(app) as client:
            for origin, expected in [("https://a.test", ["https://a.test"]), ("https://b.test", ["https://b.test"]), ("https://denied.test", [])]:
                response = await client.get("/", headers={"Origin": origin})
                assert response.status_code == status
                assert response.headers.get_list("access-control-allow-origin") == expected


@pytest.mark.asyncio
async def test_reused_response_preserves_user_headers_and_isolates_send_mutation():
    response = TachyonJSONResponse({"ok": True})
    response.headers["x-user"] = "kept"
    app = Tachyon()
    app.add_middleware(CORSMiddleware, allow_origins=["https://a.test"])
    @app.get("/")
    async def endpoint():
        return response
    async with create_client(app) as client:
        allowed = await client.get("/", headers={"Origin": "https://a.test"})
        denied = await client.get("/", headers={"Origin": "https://denied.test"})
    assert allowed.headers["x-user"] == denied.headers["x-user"] == "kept"
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["body_first", "dependency_first"])
async def test_injected_request_shares_json_body_cache(order):
    app = Tachyon()
    async def read_body(request: Request):
        return await request.json()
    if order == "body_first":
        @app.post("/")
        async def endpoint(data: dict = Body(), duplicate=Depends(read_body)):
            return {"same": data == duplicate}
    else:
        @app.post("/")
        async def endpoint(duplicate=Depends(read_body), data: dict = Body()):
            return {"same": data == duplicate}
    async with create_client(app) as client:
        response = await asyncio.wait_for(client.post("/", json={"x": 1}), 2)
    assert response.status_code == 200 and response.json() == {"same": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("injection", ["body", "request", "form"])
async def test_chunked_body_limit_stops_consumption_at_first_excess(injection):
    app = Tachyon(max_body_size=4)
    if injection == "body":
        @app.post("/")
        async def endpoint(data: dict = Body()):
            return data
    elif injection == "request":
        @app.post("/")
        async def endpoint(request: Request):
            return await request.json()
    else:
        @app.post("/")
        async def endpoint(value: str = Form(...)):
            return value
    received = 0
    messages = []
    async def receive():
        nonlocal received
        received += 1
        return {"type": "http.request", "body": b"12345", "more_body": True}
    async def send(message):
        messages.append(message)
    await app(scope(method="POST", headers=[(b"content-type", b"application/x-www-form-urlencoded")]), receive, send)
    assert received == 1
    assert messages[0]["status"] == 422


@pytest.mark.asyncio
async def test_body_disconnect_does_not_loop_or_parse_empty_json():
    app = Tachyon()
    @app.post("/")
    async def endpoint(data: dict = Body()):
        return data
    received = 0
    messages = []
    async def receive():
        nonlocal received
        received += 1
        return {"type": "http.disconnect"}
    async def send(message):
        messages.append(message)
    await asyncio.wait_for(app(scope(method="POST"), receive, send), 2)
    assert received == 1 and messages[0]["status"] == 422


@pytest.mark.asyncio
async def test_form_types_alias_and_list_validation():
    app = Tachyon()
    @app.post("/")
    async def endpoint(number: int = Form(..., alias="n"), flags: list[bool] = Form(...)):
        return {"number": number, "flags": flags}
    async with create_client(app) as client:
        response = await client.post("/", content="n=3&flags=true&flags=false", headers={"content-type": "application/x-www-form-urlencoded"})
        invalid = await client.post("/", data={"n": "bad", "flags": "true"})
    assert response.json() == {"number": 3, "flags": [True, False]}
    assert invalid.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
async def test_uploads_close_after_response_and_background(fail):
    app = Tachyon()
    uploads = []
    seen = []
    @app.post("/")
    async def endpoint(bg: BackgroundTasks, upload=File(...), number: int = Form(...)):
        uploads.append(upload)
        bg.add_task(lambda: seen.append(upload.file.closed))
        if fail:
            raise HTTPException(400, "rejected")
        return {"name": upload.filename}
    async with create_client(app) as client:
        response = await client.post("/", files={"upload": ("sample.txt", b"abc")}, data={"number": "3"})
    assert response.status_code == (400 if fail else 200)
    assert uploads[0].file.closed
    assert seen == ([] if fail else [False])


@pytest.mark.asyncio
async def test_multipart_limit_closes_partially_parsed_file(monkeypatch):
    import starlette.formparsers as parsers
    opened = []
    original = parsers.SpooledTemporaryFile
    def create_file(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file
    monkeypatch.setattr(parsers, "SpooledTemporaryFile", create_file)
    header = b'--audit\r\nContent-Disposition: form-data; name="upload"; filename="a.txt"\r\nContent-Type: text/plain\r\n\r\nsmall'
    app = Tachyon(max_body_size=len(header) + 10)
    @app.post("/")
    async def endpoint(upload=File(...)):
        return {"ok": True}
    chunks = iter([header, b"x" * 1024])
    messages = []
    async def receive():
        return {"type": "http.request", "body": next(chunks), "more_body": True}
    async def send(message):
        messages.append(message)
    await app(scope(method="POST", headers=[(b"content-type", b"multipart/form-data; boundary=audit")]), receive, send)
    assert messages[0]["status"] == 422
    assert all(file.closed for file in opened)


@pytest.mark.asyncio
@pytest.mark.parametrize("custom", [False, True])
async def test_background_tasks_run_after_response_preserving_existing_background(custom):
    events = []
    loop_thread = threading.get_ident()
    app = Tachyon()
    @app.get("/")
    async def endpoint(bg: BackgroundTasks):
        bg.add_task(lambda: events.append(("task", threading.get_ident() != loop_thread)))
        if custom:
            return JSONResponse({"ok": True}, background=BackgroundTask(lambda: events.append("existing")))
        return {"ok": True}
    async def receive():
        return {"type": "http.request", "body": b""}
    async def send(message):
        events.append(message["type"])
    await app(scope(), receive, send)
    assert events[:2] == ["http.response.start", "http.response.body"]
    assert events[2:] == (["existing"] if custom else []) + [("task", True)]


@pytest.mark.asyncio
@pytest.mark.parametrize("has_params", [False, True])
async def test_sync_endpoints_run_off_event_loop(has_params):
    loop_thread = threading.get_ident()
    app = Tachyon()
    if has_params:
        @app.get("/")
        def endpoint(value: int = Query(3)):
            return {"worker": threading.get_ident() != loop_thread, "value": value}
    else:
        @app.get("/")
        def endpoint():
            return {"worker": threading.get_ident() != loop_thread, "value": 3}
    async with create_client(app) as client:
        response = await client.get("/")
    assert response.json() == {"worker": True, "value": 3}


@pytest.mark.asyncio
async def test_send_failure_does_not_start_second_response():
    app = Tachyon()
    @app.get("/")
    async def endpoint():
        return {"ok": True}
    events = []
    async def receive():
        return {"type": "http.request", "body": b""}
    async def send(message):
        events.append(message["type"])
        if message["type"] == "http.response.body":
            raise OSError("connection lost")
    with pytest.raises(OSError, match="connection lost"):
        await app(scope(), receive, send)
    assert events == ["http.response.start", "http.response.body"]


@pytest.mark.asyncio
async def test_unhandled_exception_logs_traceback(caplog):
    app = Tachyon()
    @app.get("/")
    async def endpoint():
        raise ValueError("traceable failure")
    async with create_client(app) as client:
        response = await client.get("/")
    assert response.status_code == 500
    assert any(record.exc_info and "traceable failure" in str(record.exc_info[1]) for record in caplog.records)


@pytest.mark.asyncio
async def test_serialization_preserves_shared_payload():
    class Item(Struct):
        value: int
    item = Item(3)
    shared = {"item": item}
    app = Tachyon()
    @app.get("/")
    async def endpoint():
        return shared
    async with create_client(app) as client:
        assert (await client.get("/")).json() == {"item": {"value": 3}}
    assert shared["item"] is item


def test_lifespan_state_and_shutdown_after_exception():
    closed = []
    @asynccontextmanager
    async def lifespan(app):
        try:
            yield {"db": "ready"}
        finally:
            closed.append(True)
    app = Tachyon(lifespan=lifespan)
    @app.get("/")
    async def endpoint(request: Request):
        return {"db": request.state.db}
    with TestClient(app) as client:
        assert client.get("/").json() == {"db": "ready"}
    assert closed == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize("number", ["999999999999999999999999999999", "１２３", "1_000", " 42 "])
async def test_numeric_conversion_matches_python_in_both_engines(number):
    app = Tachyon()
    @app.get("/query")
    async def query(value: int = Query(...)):
        return {"value": str(value)}
    @app.get("/path/{value}")
    async def path(value: int):
        return {"value": str(value)}
    async with create_client(app) as client:
        assert (await client.get("/query", params={"value": number})).json() == {"value": str(int(number))}
        assert (await client.get("/path/" + number)).json() == {"value": str(int(number))}


def test_invalid_configuration_fails_at_registration():
    with pytest.raises(ValueError, match="max_body_size"):
        Tachyon(max_body_size=-1)
    app = Tachyon()
    with pytest.raises(TypeError, match="Cannot bind required"):
        @app.get("/")
        async def endpoint(required: str):
            return required
    with pytest.raises(TypeError, match="Unsupported route options"):
        @app.get("/", unsupported=True)
        async def unknown():
            return {}


@pytest.mark.asyncio
async def test_route_dependencies_preserve_router_authorization():
    async def deny():
        raise HTTPException(401, "denied")
    async def other():
        return "other"
    router = Router(dependencies=[Depends(deny)])
    @router.get("/", dependencies=[Depends(other)])
    async def endpoint():
        return {"secret": True}
    app = Tachyon()
    app.include_router(router)
    async with create_client(app) as client:
        assert (await client.get("/")).status_code == 401


@pytest.mark.asyncio
async def test_shared_response_does_not_replay_request_tasks():
    app = Tachyon()
    response = TachyonJSONResponse({"ok": True})
    calls = []
    @app.get("/")
    async def endpoint(bg: BackgroundTasks, value: int = Query(...)):
        bg.add_task(calls.append, value)
        return response
    async with create_client(app) as client:
        await client.get("/?value=1")
        await client.get("/?value=2")
    assert calls == [1, 2]
    assert response.background is None


@pytest.mark.asyncio
async def test_fast_path_exception_handler_obeys_body_limit():
    app = Tachyon(max_body_size=4)
    @app.exception_handler(ValueError)
    async def handler(request, exc):
        return JSONResponse({"size": len(await request.body())})
    @app.post("/")
    async def endpoint():
        raise ValueError("expected")
    async with create_client(app) as client:
        response = await client.post("/", content=b"x" * 100)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_disconnect_during_form_read_creates_no_files(monkeypatch):
    import starlette.formparsers as parsers
    opened = []
    original = parsers.SpooledTemporaryFile
    def create_file(*args, **kwargs):
        handle = original(*args, **kwargs)
        opened.append(handle)
        return handle
    monkeypatch.setattr(parsers, "SpooledTemporaryFile", create_file)
    header = b'--audit\r\nContent-Disposition: form-data; name="upload"; filename="a.txt"\r\n\r\nsmall'
    app = Tachyon()
    @app.post("/")
    async def endpoint(upload=File(...)):
        return {}
    chunks = iter([{"type": "http.request", "body": header, "more_body": True}, {"type": "http.disconnect"}])
    messages = []
    async def receive():
        return next(chunks)
    async def send(message):
        messages.append(message)
    await app(scope(method="POST", headers=[(b"content-type", b"multipart/form-data; boundary=audit")]), receive, send)
    assert messages[0]["status"] == 422
    assert not opened
