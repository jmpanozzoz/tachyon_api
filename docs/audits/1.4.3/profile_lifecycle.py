"""Validated lifecycle workloads omitted from the eight async happy-path cases.

Run from a baseline/candidate checkout root. Batch timings include driver checks,
not network capacity or per-request latency percentiles.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path.cwd()))

from benchmark.profile_hotpath import make_call  # noqa: E402
from starlette.requests import ClientDisconnect  # noqa: E402
from starlette.responses import StreamingResponse  # noqa: E402
from tachyon_api import Body, Depends, Tachyon  # noqa: E402


async def run(output):
    apps = {name: Tachyon() for name in ("sync_endpoint", "sync_factory", "middleware", "routes_1000", "stream")}

    def sync_endpoint():
        return {"ok": True}

    async def hello():
        return {"ok": True}

    async def factory_endpoint(value=Depends(sync_endpoint)):
        return value

    state = {"closed": 0}

    async def producer():
        try:
            yield b'{"ok":'
            yield b'true}'
        finally:
            state["closed"] += 1

    async def stream_endpoint():
        return StreamingResponse(producer(), media_type="application/json")

    class Noop:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)

    apps["sync_endpoint"].get("/")(sync_endpoint)
    apps["sync_factory"].get("/")(factory_endpoint)
    apps["middleware"].add_middleware(Noop)
    apps["middleware"].add_middleware(Noop)
    apps["middleware"].get("/")(hello)
    apps["stream"].get("/")(stream_endpoint)
    for index in range(1000):
        apps["routes_1000"].get(f"/rows/{index}", include_in_schema=False)(hello)
    calls = {name: make_call(app, (name, "GET", "/rows/999" if name == "routes_1000" else "/", None, {}, {"ok": True}))
             for name, app in apps.items()}
    rejected = Tachyon(max_body_size=1)

    @rejected.post("/")
    async def body_endpoint(body: int = Body()):
        raise AssertionError("Oversized request reached endpoint")

    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"}, "http_version": "1.1",
             "method": "POST", "scheme": "http", "path": "/", "root_path": "", "query_string": b"",
             "headers": [(b"content-length", b"2")], "server": ("test", 80), "client": ("127.0.0.1", 1234)}

    async def receive():
        raise AssertionError("Declared oversized body was read")

    async def reject_call():
        messages = []

        async def send(message):
            messages.append(message)

        await rejected(dict(scope), receive, send)
        assert messages[0]["status"] == 422
        assert dict(messages[0]["headers"])[b"connection"] == b"close"
        assert json.loads(messages[1]["body"])["code"] == "VALIDATION_ERROR"

    async def disconnect_call():
        before = state["closed"]
        starts = []

        async def send(message):
            if message["type"] == "http.response.start":
                starts.append(message)
            elif message["type"] == "http.response.body":
                raise OSError("disconnected")

        try:
            await apps["stream"]({**scope, "method": "GET", "headers": []}, receive, send)
        except ClientDisconnect:
            pass
        else:
            raise AssertionError("Expected transport failure")
        assert len(starts) == 1 and state["closed"] == before + 1

    calls.update(declared_body_rejection=reject_call, stream_disconnect=disconnect_call)
    results = {}
    for name, call in calls.items():
        for _ in range(25):
            await call()
        samples = []
        for _ in range(5):
            started = time.perf_counter_ns()
            for _ in range(1000):
                await call()
            samples.append((time.perf_counter_ns() - started) / 1000)
        results[name] = samples
    root = Path(__import__("tachyon_api").__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    output.write_text(json.dumps({"python": sys.version, "runtime_root": str(root),
        "runtime_sha256": digest.hexdigest(), "methodology": __doc__, "iterations_per_batch": 1000,
        "ns_per_validated_call": results}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args().output))
