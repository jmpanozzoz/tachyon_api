"""Transport failures must finalize async response producers and request files."""
import asyncio

import pytest
from starlette.responses import StreamingResponse
from starlette.requests import ClientDisconnect

from tachyon_api import Body, Tachyon
from tachyon_api import File, UploadFile
from tachyon_api.background import BackgroundTasks


@pytest.mark.asyncio
@pytest.mark.parametrize("with_request", [False, True])
@pytest.mark.parametrize("failure", ["disconnect", "cancel"])
async def test_failed_send_finalizes_stream_before_request_returns(with_request, failure):
    app = Tachyon()
    finalized = []
    async def chunks():
        try:
            yield b"first"
            await asyncio.sleep(3600)
        finally:
            finalized.append("closed")
    response = StreamingResponse(chunks())
    if with_request:
        @app.post("/")
        async def endpoint(data: dict = Body()):
            return response
    else:
        @app.post("/")
        async def endpoint():
            return response
    messages = []
    async def receive():
        return {"type": "http.request", "body": b"{}", "more_body": False}
    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body":
            if failure == "cancel":
                raise asyncio.CancelledError()
            raise OSError("connection closed")
    scope = {"type": "http", "method": "POST", "path": "/", "root_path": "",
             "query_string": b"", "headers": [], "asgi": {"version": "3.0", "spec_version": "2.4"}}
    try:
        with pytest.raises((ClientDisconnect, asyncio.CancelledError)):
            await app(scope, receive, send)
        assert finalized == ["closed"]
        assert sum(m["type"] == "http.response.start" for m in messages) == 1
    finally:
        # Keep a failed regression from leaving producers alive in the test loop.
        await response.body_iterator.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [b"hello", b"x" * (1024 * 1024 + 64)], ids=["memory", "spooled-disk"])
async def test_stream_finalizer_can_read_upload_before_request_cleanup(monkeypatch, content):
    import starlette.formparsers as parsers
    original = parsers.SpooledTemporaryFile
    opened, events = [], []
    def track(*args, **kwargs):
        handle = original(*args, **kwargs)
        opened.append(handle)
        return handle
    monkeypatch.setattr(parsers, "SpooledTemporaryFile", track)
    app = Tachyon()
    @app.post("/")
    async def endpoint(tasks: BackgroundTasks, upload: UploadFile = File()):
        tasks.add_task(lambda: events.append("background"))
        async def chunks():
            try:
                yield await upload.read()
            finally:
                events.append(("stream_closed", upload.file.closed))
        return StreamingResponse(chunks())
    body = b'--operational\r\nContent-Disposition: form-data; name="upload"; filename="a.txt"\r\n\r\n' + content + b'\r\n--operational--\r\n'
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    sent = []
    async def send(message):
        sent.append(message)
        if message["type"] == "http.response.body":
            raise OSError("connection closed")
    scope = {"type": "http", "method": "POST", "path": "/", "root_path": "", "query_string": b"",
             "headers": [(b"content-type", b"multipart/form-data; boundary=operational")],
             "asgi": {"version": "3.0", "spec_version": "2.4"}}
    with pytest.raises(ClientDisconnect):
        await app(scope, receive, send)
    assert events == [("stream_closed", False)]
    assert opened and all(handle.closed for handle in opened)
    if len(content) > 1024 * 1024:
        assert opened[0]._rolled
    assert [message["status"] for message in sent if message["type"] == "http.response.start"] == [200]


@pytest.mark.asyncio
async def test_task_cancellation_awaits_async_generator_finalizer():
    app = Tachyon()
    sending = asyncio.Event()
    finalized = []
    async def chunks():
        try:
            yield b"first"
        finally:
            await asyncio.sleep(.001)
            finalized.append(True)
    @app.get("/")
    async def endpoint():
        return StreamingResponse(chunks())
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        if message["type"] == "http.response.body":
            sending.set()
            await asyncio.Event().wait()
    scope = {"type": "http", "method": "GET", "path": "/", "root_path": "", "query_string": b"",
             "headers": [], "asgi": {"version": "3.0", "spec_version": "2.4"}}
    task = asyncio.create_task(app(scope, receive, send))
    await asyncio.wait_for(sending.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finalized == [True]
