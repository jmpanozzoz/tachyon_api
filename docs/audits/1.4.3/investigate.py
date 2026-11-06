"""Measure the DI shortcut and compare CORS behavior without altering runtime.

Run the same script from baseline/candidate checkout roots with the same Python.
Results describe that environment, not a stable performance or protocol budget.
"""
import argparse
import asyncio
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path.cwd()))


async def dependency():
    from tachyon_api import Tachyon
    from tests.test_continuous_di_graph import shared_graph
    module = importlib.import_module("tachyon_api.processing.dependencies._sig_cache")
    original = module.get_bindings
    classes = shared_graph(14)
    app, sentinel = Tachyon(), object()
    app.register_instance(classes[-1], sentinel)
    results = {}
    for name in ("resolve_class_dependency", "resolve_callable_dependency"):
        method = getattr(app._dependency_resolver, name)
        visits = []

        def counted(provider):
            visits.append(provider)
            return original(provider)

        module.get_bindings = counted
        try:
            assert await method(classes[-1], {}, None) is sentinel
        finally:
            module.get_bindings = original
        timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            for _ in range(1000):
                assert await method(classes[-1], {}, None) is sentinel
            timings.append((time.perf_counter_ns() - start) / 1000)
        results[name] = {"nodes": len(classes), "binding_visits": len(visits),
                         "ns_per_validated_cached_resolution": timings}
        app.dependency_overrides = {classes[0]: lambda: "request-local"}
        try:
            await method(classes[-1], {}, None)
        except TypeError as exc:
            assert "Singleton dependency cannot capture" in str(exc)
            results[name]["unsafe_replaced_override_rejected"] = True
        else:
            raise AssertionError("Unsafe singleton override was accepted")
        app.dependency_overrides.clear()
    return results


async def cors():
    from tachyon_api.middlewares.cors import CORSMiddleware
    from starlette.middleware.cors import CORSMiddleware as Reference

    async def endpoint(scope, receive, send):
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1000})
            return
        await send({"type": "http.response.start", "status": 202,
                    "headers": [(b"vary", b"Accept-Encoding")]})
        await send({"type": "http.response.body", "body": b"next"})

    origin = {"origin": "https://client.example"}
    preflight = {**origin, "access-control-request-method": "GET"}
    allowed = {"allow_origins": ["https://client.example"]}
    cases = [
        ("no-origin", allowed, "GET", {}, "http"),
        ("simple-origin", allowed, "GET", origin, "http"),
        ("unsupported-simple", allowed, "GET", {"origin": "https://other.example"}, "http"),
        ("preflight-default-get", allowed, "OPTIONS", preflight, "http"),
        ("preflight-default-delete", allowed, "OPTIONS", {**preflight, "access-control-request-method": "DELETE"}, "http"),
        ("preflight-default-head", allowed, "OPTIONS", {**preflight, "access-control-request-method": "HEAD"}, "http"),
        ("disallowed-origin", allowed, "OPTIONS", {**preflight, "origin": "https://other.example"}, "http"),
        ("disallowed-method", {**allowed, "allow_methods": ["GET"]}, "OPTIONS", {**preflight, "access-control-request-method": "DELETE"}, "http"),
        ("disallowed-header", {**allowed, "allow_headers": ["X-Allowed"]}, "OPTIONS", {**preflight, "access-control-request-headers": "X-Denied"}, "http"),
        ("allowed-header", {**allowed, "allow_headers": ["X-Allowed"]}, "OPTIONS", {**preflight, "access-control-request-headers": "X-Allowed"}, "http"),
        ("wildcard-methods", {**allowed, "allow_methods": ["*"]}, "OPTIONS", preflight, "http"),
        ("wildcard-headers", {**allowed, "allow_headers": ["*"]}, "OPTIONS", {**preflight, "access-control-request-headers": "X-Token"}, "http"),
        ("credentials", {**allowed, "allow_credentials": True}, "GET", origin, "http"),
        ("wildcard-cookie", {"allow_origins": ["*"]}, "GET", {**origin, "cookie": "sid=demo"}, "http"),
        ("wildcard-credentials", {"allow_origins": ["*"], "allow_credentials": True}, "GET", origin, "http"),
        ("exposed-headers", {**allowed, "expose_headers": ["X-Result"]}, "GET", origin, "http"),
        ("websocket", allowed, "GET", origin, "websocket"),
    ]
    results = []
    for name, config, method, headers, protocol in cases:
        observations = {}
        for implementation, cls in (("tachyon", CORSMiddleware), ("starlette", Reference)):
            messages = []

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                messages.append(message)

            await cls(endpoint, **config)({"type": protocol, "method": method,
                "headers": [(key.encode(), value.encode()) for key, value in headers.items()]}, receive, send)
            observations[implementation] = [{key: (value.decode() if isinstance(value, bytes) else
                [(k.decode().lower(), v.decode()) for k, v in value] if key == "headers" else value)
                for key, value in message.items()} for message in messages]
        results.append({"case": name, "config": config, **observations,
                        "identical_messages": observations["tachyon"] == observations["starlette"]})
    return results


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("dependency", "cors"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(importlib.import_module("tachyon_api").__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    result = {"python": sys.version, "platform": platform.platform(),
              "runtime_root": str(root), "runtime_sha256": digest.hexdigest(),
              "versions": {name: importlib.metadata.version(name) for name in ("starlette", "msgspec")},
              "methodology": "DI: 15-node warm singleton, five batches of 1000 verified resolutions, no driver subtraction. CORS: direct ASGI message comparison, including representation differences; differences are not automatic security defects.",
              "observations": await (dependency() if args.target == "dependency" else cors())}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    asyncio.run(main())
