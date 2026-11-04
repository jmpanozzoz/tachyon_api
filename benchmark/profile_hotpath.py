"""Validate and time the full async ASGI request path without a network server."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import statistics
import sys
import time

from benchmark.scenarios import SCENARIOS


def make_call(app, scenario):
    _, method, target, payload, headers, expected = scenario
    path, _, query = target.partition("?")
    body = json.dumps(payload).encode() if payload is not None else b""
    base = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": method, "scheme": "http", "path": path,
            "raw_path": path.encode(), "root_path": "", "query_string": query.encode(),
            "server": ("test", 80), "client": ("127.0.0.1", 10000),
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()] +
                       [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]}
    async def call():
        messages = []
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        async def send(message):
            messages.append(message)
        await app(dict(base), receive, send)
        starts = [message for message in messages if message["type"] == "http.response.start"]
        assert len(starts) == 1 and starts[0]["status"] == 200
        assert b"application/json" in dict(starts[0]["headers"])[b"content-type"]
        data = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        assert json.loads(data) == expected
    return call


async def run(args):
    from benchmark.app_tachyon import app
    import tachyon_api
    import tachyon_api.routing.trie as trie
    root = Path(tachyon_api.__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    versions = {}
    for name in ("tachyon-api", "starlette", "msgspec", "orjson"):
        versions[name] = importlib.metadata.version(name)
    report = {"python": sys.version, "platform": platform.platform(), "versions": versions,
        "runtime_root": str(root), "trie_origin": trie.__file__, "runtime_sha256": digest.hexdigest(),
        "iterations": args.iterations, "repetitions": args.repeats, "measurements": [],
        "methodology": "Full single-task ASGI requests using fresh scope and send buffer, shared valid scenarios and async endpoints. Every status/content-type/JSON result is checked, including timed requests. Includes Python driver/validation costs; excludes networking and server. GC stays enabled. Repeated hot inputs, not production access patterns. Not throughput capacity or isolated framework overhead."}
    calls = {scenario[0]: make_call(app, scenario) for scenario in SCENARIOS}
    for call in calls.values():
        for _ in range(50):
            await call()
    for repeat in range(args.repeats):
        order = list(calls)
        random.Random(142 + repeat).shuffle(order)
        for name in order:
            started = time.perf_counter_ns()
            for _ in range(args.iterations):
                await calls[name]()
            report["measurements"].append({"scenario": name, "repeat": repeat,
                "ns_per_validated_request": (time.perf_counter_ns() - started) / args.iterations})
    report["medians_ns"] = {name: statistics.median(row["ns_per_validated_request"]
        for row in report["measurements"] if row["scenario"] == name) for name in calls}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"versions": versions, "medians_ns": report["medians_ns"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.iterations, args.repeats) < 1:
        parser.error("iterations and repeats must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
