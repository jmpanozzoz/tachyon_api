"""Optional real-network contracts, including lifespan and graceful shutdown."""
import importlib.util
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import time
import socket
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from benchmark.run_benchmark import free_port
from benchmark.server import server_command

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Graceful shutdown contract uses POSIX signals")


@contextmanager
def running_server(name, folder):
    if importlib.util.find_spec(name) is None or importlib.util.find_spec("websockets") is None:
        pytest.skip(f"Install {name} and websockets to run real-server contracts")
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
                yield client, port, process
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            assert stopped.exists(), "server did not finish application shutdown"


@pytest.fixture(scope="module", params=["uvicorn", "granian"])
def server(request, tmp_path_factory):
    with running_server(request.param, tmp_path_factory.mktemp(request.param)) as (client, port, _):
        yield client, port


def wait_for_event(client, expected):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if expected in client.get("/events").json():
            return
        time.sleep(.025)
    pytest.fail(f"Missing server event: {expected}")


def test_lifespan_body_and_limit(server):
    client, _ = server
    assert client.get("/health").json() == {"ready": True}
    assert client.post("/body", content=b"hello").json() == {"bytes": 5}
    assert client.post("/body", content=b"x" * (64 * 1024 + 1)).status_code == 422


def test_rejected_body_does_not_leave_an_unusable_keepalive_connection(server):
    client, _ = server
    for _ in range(10):
        response = client.post("/body", content=b"x" * (64 * 1024 + 1))
        assert response.status_code == 422
        assert response.headers.get("connection") == "close"
        assert client.get("/stream").text == "first\nsecond\n"


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


def test_disconnect_finalizes_stream_and_server_keeps_serving(server):
    client, _ = server
    with client.stream("GET", "/abort-stream/disconnect") as response:
        assert response.status_code == 200
        assert next(response.iter_bytes())
    wait_for_event(client, {"producer_closed": "disconnect"})
    wait_for_event(client, {"finished": "/abort-stream/disconnect"})
    assert client.get("/health").json() == {"ready": True}


def test_disconnected_upload_stream_finalizes_before_file_cleanup(server):
    client, _ = server
    with client.stream("POST", "/upload-stream/upload", files={"file": ("hello.txt", b"hello")}) as response:
        assert response.status_code == 200
        assert next(response.iter_bytes())
    wait_for_event(client, {"upload_producer_closed": "upload", "file_closed": False})
    wait_for_event(client, {"finished": "/upload-stream/upload"})


def test_repeated_incomplete_uploads_do_not_leave_requests_running(server):
    client, port = server
    for index in range(10):
        path = f"/abort-upload/{index}"
        with socket.create_connection(("127.0.0.1", port), timeout=3) as connection:
            connection.sendall((f"POST {path} HTTP/1.1\r\nHost: localhost\r\nContent-Length: 60000\r\n"
                                "Content-Type: multipart/form-data; boundary=abort\r\n\r\n").encode())
            connection.sendall(b'--abort\r\nContent-Disposition: form-data; name="file"; filename="a.txt"\r\n\r\npartial')
        wait_for_event(client, {"finished": path})
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("name", ["uvicorn", "granian"])
def test_shutdown_drains_request_before_lifespan_cleanup(name, tmp_path):
    with running_server(name, tmp_path) as (client, port, process):
        def pending_request():
            with httpx.Client(timeout=5) as pending:
                return pending.get(f"http://127.0.0.1:{port}/drain/shutdown")
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(pending_request)
            wait_for_event(client, {"inflight": "shutdown"})
            process.terminate()
            response = future.result(timeout=5)
        assert response.status_code == 200
        assert response.json() == {"drained": "shutdown"}
        process.wait(timeout=10)
