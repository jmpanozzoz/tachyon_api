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
    yield
    Path(os.environ["TACHYON_SERVER_SHUTDOWN"]).write_text("stopped")


app = Tachyon(lifespan=lifespan, max_body_size=64 * 1024)


@app.get("/health")
async def health():
    return {"ready": app.state.ready}


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
