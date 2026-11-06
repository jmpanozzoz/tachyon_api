"""Request resource ownership under validation, transmission and cancellation."""
import asyncio
import threading
from contextlib import asynccontextmanager
from functools import partial, wraps

import anyio
import pytest
from starlette.exceptions import HTTPException
from starlette.responses import StreamingResponse

from tachyon_api import Depends, Tachyon, injectable
from tachyon_api.background import BackgroundTasks
from tests.helpers import create_client


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["sync", "async", "partial", "callable", "wrapped"])
async def test_lifo_cached_resources_survive_stream_and_background(kind):
    events = []
    loop_thread = threading.get_ident()

    def sync_resource():
        assert threading.get_ident() != loop_thread
        events.append("open")
        try:
            yield []
        finally:
            assert threading.get_ident() != loop_thread
            events.append("close")

    async def async_resource():
        events.append("open")
        try:
            yield []
        except BaseException:
            events.append("unexpected-error")
            raise
        finally:
            await anyio.sleep(0)
            events.append("close")

    class Callable:
        async def __call__(self):
            async with asynccontextmanager(async_resource)() as value:
                yield value

    @wraps(async_resource)
    def wrapped():
        return async_resource()

    resource = {"sync": sync_resource, "async": async_resource,
                "partial": partial(sync_resource), "callable": Callable(), "wrapped": wrapped}[kind]

    async def nested(value=Depends(resource)):
        events.append("nested-open")
        try:
            yield value
        finally:
            events.append("nested-close")

    app = Tachyon()

    @app.get("/")
    async def endpoint(tasks: BackgroundTasks, a=Depends(nested), b=Depends(resource)):
        assert a is b
        async def body():
            events.append("stream")
            yield b"ok"
        async def task():
            events.append("background")
            a.append("used")
        tasks.add_task(task)
        return StreamingResponse(body())

    async with create_client(app) as client:
        for _ in range(2):
            assert (await client.get("/")).text == "ok"
    assert events == ["open", "nested-open", "stream", "background", "nested-close", "close"] * 2


@pytest.mark.asyncio
async def test_partial_acquisition_and_original_error_reach_cleanup(caplog):
    events = []
    async def resource():
        try:
            yield "value"
        except HTTPException as exc:
            events.append(exc.status_code)
            raise
        finally:
            events.append("closed")
            raise RuntimeError("cleanup failed")

    async def failing(value=Depends(resource)):
        raise HTTPException(409, "conflict")

    app = Tachyon()
    @app.get("/")
    async def endpoint(value=Depends(failing)):
        pytest.fail("handler must not run")

    async with create_client(app) as client:
        assert (await client.get("/")).status_code == 409
    assert events == [409, "closed"]
    assert "Dependency cleanup failed" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("yields", [0, 2])
async def test_invalid_yield_count_is_not_silently_accepted(yields):
    async def resource():
        for value in range(yields):
            yield value
    app = Tachyon()
    @app.get("/")
    async def endpoint(value=Depends(resource)):
        return value
    async with create_client(app) as client:
        if yields == 0:
            assert (await client.get("/")).status_code == 500
        else:
            with pytest.raises(RuntimeError, match="didn't stop"):
                await client.get("/")


def scope():
    return {"type": "http", "method": "GET", "path": "/", "root_path": "",
            "headers": [], "query_string": b"", "http_version": "1.1",
            "scheme": "http", "server": ("test", 80), "client": ("test", 1),
            "asgi": {"version": "3.0", "spec_version": "2.4"}}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["send", "cancel"])
async def test_transport_and_cancel_close_once_without_second_response(failure):
    events, messages = [], []
    ready = asyncio.Event()
    async def resource():
        try:
            yield "active"
        finally:
            await anyio.sleep(0)
            events.append("closed")
    app = Tachyon()
    @app.get("/")
    async def endpoint(value=Depends(resource)):
        ready.set()
        if failure == "cancel":
            await anyio.sleep_forever()
        return value
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        messages.append(message)
        raise OSError("client disconnected")
    task = asyncio.create_task(app(scope(), receive, send))
    await asyncio.wait_for(ready.wait(), 2)
    if failure == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert messages == []
    else:
        with pytest.raises(OSError, match="disconnected"):
            await task
        assert len(messages) == 1
    assert events == ["closed"]


@pytest.mark.asyncio
async def test_request_class_override_and_concurrent_isolation():
    active, closed = set(), []
    async def resource():
        value = object()
        active.add(value)
        try:
            yield value
        finally:
            active.remove(value)
            closed.append(value)
    @injectable(scope="request")
    class Service:
        def __init__(self, value=Depends(resource)):
            self.value = value
    app = Tachyon()
    @app.get("/")
    async def endpoint(service: Service = Depends()):
        await anyio.sleep(.01)
        assert service.value in active
        return {"ok": True}
    async with create_client(app) as client:
        results = await asyncio.gather(*(client.get("/") for _ in range(8)))
        assert all(r.status_code == 200 for r in results)
        async def override():
            async with asynccontextmanager(resource)() as value:
                yield value
        app.dependency_overrides[resource] = override
        assert (await client.get("/")).status_code == 200
    assert not active
    assert len(set(closed)) == 9


def test_websocket_rejects_nested_generators_at_registration():
    async def resource():
        yield "value"
    def nested(value=Depends(resource)):
        return value
    app = Tachyon()
    with pytest.raises(TypeError, match="require an HTTP request"):
        @app.websocket("/")
        async def endpoint(websocket, value=Depends(nested)):
            pass


@pytest.mark.asyncio
async def test_cleanup_timeout_does_not_skip_outer_exit(monkeypatch):
    monkeypatch.setattr("tachyon_api.processing.scope.DEPENDENCY_CLEANUP_TIMEOUT", .01)
    events = []
    async def outer():
        try:
            yield "outer"
        finally:
            events.append("outer-close")
    async def inner(value=Depends(outer)):
        try:
            yield value
        finally:
            await anyio.sleep_forever()
    app = Tachyon()
    @app.get("/")
    async def endpoint(value=Depends(inner)):
        return value
    async with create_client(app) as client:
        with pytest.raises(TimeoutError):
            await client.get("/")
    assert events == ["outer-close"]


@pytest.mark.asyncio
async def test_sync_exit_does_not_deadlock_with_saturated_default_pool():
    limiter = anyio.to_thread.current_default_thread_limiter()
    previous = limiter.total_tokens
    limiter.total_tokens = 1
    entered, release = threading.Event(), threading.Event()
    events = []
    def resource():
        try:
            yield "value"
        finally:
            events.append("closed")
            release.set()
    def blocked_thread():
        entered.set()
        assert release.wait(2)
    app = Tachyon()
    tasks = []
    @app.get("/")
    async def endpoint(value=Depends(resource)):
        tasks.append(asyncio.create_task(anyio.to_thread.run_sync(blocked_thread)))
        while not entered.is_set():
            await anyio.sleep(.001)
        return value
    try:
        async with create_client(app) as client:
            with anyio.fail_after(3):
                assert (await client.get("/")).status_code == 200
        await asyncio.gather(*tasks)
    finally:
        release.set()
        limiter.total_tokens = previous
    assert events == ["closed"]


def test_bootstrap_override_rejects_generator_without_creating_it():
    @injectable
    class Service:
        pass
    def resource():
        yield "value"
    app = Tachyon()
    app.dependency_overrides[Service] = resource
    with pytest.raises(TypeError, match="require an HTTP request"):
        app._dependency_resolver.resolve_dependency(Service)
