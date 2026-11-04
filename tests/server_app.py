"""Application exercised through real optional ASGI servers."""
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.websockets import WebSocket

from tachyon_api import File, Tachyon, UploadFile


@asynccontextmanager
async def lifespan(app):
    app.state.ready = True
    app.state.events = []
    yield
    Path(os.environ["TACHYON_SERVER_SHUTDOWN"]).write_text("stopped")


app = Tachyon(lifespan=lifespan, max_body_size=64 * 1024)


class ObserveCompletion:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        try:
            await self.app(scope, receive, send)
        finally:
            if scope["type"] == "http" and scope["path"].startswith(("/abort-", "/upload-stream/", "/drain/")):
                scope["app"].state.events.append({"finished": scope["path"]})


app.add_middleware(ObserveCompletion)


@app.get("/health")
async def health():
    return {"ready": app.state.ready}


@app.get("/events")
async def events():
    return app.state.events


@app.post("/body")
async def body(request: Request):
    return {"bytes": len(await request.body())}


@app.post("/upload")
async def upload(file: UploadFile = File()):
    return {"filename": file.filename, "data": (await file.read()).decode()}


@app.get("/stream")
async def stream():
    async def chunks():
        yield b"first\n"
        await asyncio.sleep(.001)
        yield b"second\n"
    return StreamingResponse(chunks(), media_type="text/plain")


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    await ws.send_text(await ws.receive_text())
    await ws.close()


@app.get("/abort-stream/{marker}")
async def abort_stream(marker: str):
    async def chunks():
        try:
            while True:
                yield b"x" * 65536
                await asyncio.sleep(.005)
        finally:
            app.state.events.append({"producer_closed": marker})
    return StreamingResponse(chunks())


@app.post("/abort-upload/{marker}")
async def abort_upload(marker: str, file: UploadFile = File()):
    return {"bytes": len(await file.read())}


@app.post("/upload-stream/{marker}")
async def upload_stream(marker: str, file: UploadFile = File()):
    async def chunks():
        try:
            yield await file.read()
            while True:
                yield b"x" * 65536
                await asyncio.sleep(.005)
        finally:
            app.state.events.append({"upload_producer_closed": marker, "file_closed": file.file.closed})
    return StreamingResponse(chunks())


@app.get("/drain/{marker}")
async def drain(marker: str):
    app.state.events.append({"inflight": marker})
    await asyncio.sleep(.25)
    return {"drained": marker}
