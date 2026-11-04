"""Optional real-network contracts, including lifespan and graceful shutdown."""
import importlib.util
import os
from pathlib import Path
import subprocess
import time

import httpx
import pytest

from benchmark.run_benchmark import free_port
from benchmark.server import server_command

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Graceful shutdown contract uses POSIX signals")


@pytest.fixture(scope="module", params=["uvicorn", "granian"])
def server(request, tmp_path_factory):
    name = request.param
    if importlib.util.find_spec(name) is None or importlib.util.find_spec("websockets") is None:
        pytest.skip(f"Install {name} and websockets to run real-server contracts")
    folder = tmp_path_factory.mktemp(name)
    stopped = folder / "shutdown"
    port = free_port()
    command = server_command(name, "tests.server_app:app", port, lifespan=True)
    with (folder / "server.log").open("w+") as log:
        process = subprocess.Popen(command, cwd=Path(__file__).resolve().parents[1],
                                   env=dict(os.environ, TACHYON_SERVER_SHUTDOWN=str(stopped)),
                                   stdout=log, stderr=log)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3) as client:
                deadline = time.monotonic() + 15
                while True:
                    if process.poll() is not None:
                        log.seek(0)
                        pytest.fail(log.read())
                    try:
                        response = client.get("/health")
                        if response.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if time.monotonic() >= deadline:
                        pytest.fail("ASGI server did not become ready")
                    time.sleep(.05)
                yield client, port
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            assert stopped.exists(), "server did not finish application shutdown"


def test_lifespan_body_and_limit(server):
    client, _ = server
    assert client.get("/health").json() == {"ready": True}
    assert client.post("/body", content=b"hello").json() == {"bytes": 5}
    assert client.post("/body", content=b"x" * (64 * 1024 + 1)).status_code == 422


def test_stream_and_multipart(server):
    client, _ = server
    response = client.get("/stream")
    assert response.status_code == 200
    assert response.text == "first\nsecond\n"
    response = client.post("/upload", files={"file": ("hello.txt", b"hello")})
    assert response.status_code == 200, response.text
    assert response.json() == {"filename": "hello.txt", "data": "hello"}


def test_websocket_round_trip(server):
    connection = pytest.importorskip("websockets.sync.client")
    _, port = server
    with connection.connect(f"ws://127.0.0.1:{port}/ws", open_timeout=3) as ws:
        ws.send("tachyon")
        assert ws.recv(timeout=3) == "tachyon"
