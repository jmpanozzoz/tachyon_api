"""Read-only behavior probes for the proposed 1.4.3 simplification.

Run from the checkout with a supported Python and installed test dependencies:
python docs/audits/1.4.3/simplification_probes.py > /tmp/simplification.json
These observations describe the baseline; they are not acceptance tests for fixes.
"""
import asyncio
from collections import Counter
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import msgspec  # noqa: E402
from tachyon_api import Tachyon  # noqa: E402
from tachyon_api.middlewares.cors import CORSMiddleware  # noqa: E402
from tachyon_api.processing._extractors.body import BodyExtractor  # noqa: E402
from tests.test_continuous_di_graph import shared_graph  # noqa: E402


async def invoke(app, kind="http", path="/", headers=(), method="GET"):
    messages = []
    scope = {
        "type": kind, "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1", "method": method, "scheme": "http",
        "path": path, "raw_path": path.encode(), "root_path": "",
        "query_string": b"", "headers": list(headers),
        "server": ("test", 80), "client": ("127.0.0.1", 1234),
    }

    async def receive():
        if kind == "websocket":
            return {"type": "websocket.connect"}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    return messages


async def middleware_probe():
    trace, constructions = [], []

    class Recorder:
        def __init__(self, app, name):
            self.app, self.name = app, name
            constructions.append(name)

        async def __call__(self, scope, receive, send):
            trace.append(self.name)
            await self.app(scope, receive, send)

    app = Tachyon()
    app.add_middleware(Recorder, name="A")
    app.add_middleware(Recorder, name="B")
    after_registration = list(constructions)
    await invoke(app)
    http = list(trace)
    trace.clear()
    await invoke(app, "websocket")
    return {"http_order": http, "websocket_order": trace,
            "constructors_at_registration": after_registration,
            "constructors_after_both_protocols": constructions}


async def dependency_probe():
    module = importlib.import_module("tachyon_api.processing.dependencies._sig_cache")
    original = module.get_bindings
    classes = shared_graph(14)
    app = Tachyon()
    sentinel = object()
    app.register_instance(classes[-1], sentinel)
    visits = []

    def counted(provider):
        visits.append(provider.__name__)
        return original(provider)

    module.get_bindings = counted
    try:
        results = []
        for _ in range(3):
            visits.clear()
            assert await app._dependency_resolver.resolve_class_dependency(classes[-1], {}, None) is sentinel
            results.append(len(visits))
        return {"nodes": len(classes), "binding_visits_per_cached_resolution": results}
    finally:
        module.get_bindings = original


async def cors_probe():
    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"vary", b"Accept-Encoding")]})
        await send({"type": "http.response.body", "body": b"ok"})

    from starlette.middleware.cors import CORSMiddleware as StarletteCORS
    results = {}
    for name, cls in (("tachyon", CORSMiddleware), ("starlette", StarletteCORS)):
        app = cls(endpoint, allow_origins=["https://client.example"],
                  allow_methods=["GET"], allow_headers=["X-Allowed"])
        messages = await invoke(app, headers=[(b"origin", b"https://client.example"),
            (b"access-control-request-method", b"DELETE"),
            (b"access-control-request-headers", b"X-Denied")], method="OPTIONS")
        preflight = messages[0]
        messages = await invoke(app, headers=[(b"origin", b"https://client.example")])
        results[name] = {"disallowed_preflight_status": preflight["status"],
            "vary_headers": [value.decode() for key, value in messages[0]["headers"] if key == b"vary"]}
    return results


def decode_probe():
    module = importlib.import_module("tachyon_api.processing._extractors.body")
    original = getattr(module, "_msgspec_validation_response", None)
    called = []

    def counted(exc):
        called.append(type(exc).__name__)
        return original(exc)

    if original is not None:
        module._msgspec_validation_response = counted
    try:
        _, response = BodyExtractor._decode(b'"wrong type"', msgspec.json.Decoder(int))
        return {"validation_is_decode_subclass": issubclass(msgspec.ValidationError, msgspec.DecodeError),
                "validation_handler_present": original is not None,
                "validation_handler_calls": called, "response": json.loads(response.body)}
    finally:
        if original is not None:
            module._msgspec_validation_response = original


async def docs_probe():
    app = Tachyon()

    @app.get("/docs")
    async def custom_docs():
        return {"custom": True}

    before = len(app.routes)
    try:
        messages = await invoke(app, path="/docs")
    except ValueError as exc:
        assert "conflicts with a documentation route" in str(exc)
        return {"conflict_rejected": str(exc), "routes_before_first_request": before,
                "routes_after": len(app.routes), "setup_done": app._docs_routes.setup_done}
    content_type = dict(messages[0]["headers"])[b"content-type"].decode()
    return {"routes_before_first_request": before, "routes_after": len(app.routes),
            "get_docs_registry_entries": sum(route["path"] == "/docs" for route in app.routes),
            "served_content_type": content_type}


async def main():
    files = [Path(name) for name in subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()]
    runtime = sorted((ROOT / "tachyon_api").rglob("*.py"))
    report = {
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "python": sys.version, "platform": platform.platform(),
        "runtime_origin": str(importlib.import_module("tachyon_api").__file__),
        "versions": {name: importlib.metadata.version(name) for name in
                     ("starlette", "msgspec", "orjson", "uvicorn", "typer", "pytest")},
        "inventory": {"tracked_files": len(files), "runtime_modules": len(runtime),
                      "runtime_lines": sum(len(path.read_text().splitlines()) for path in runtime),
                      "tracked_by_top_level": dict(Counter(path.parts[0] for path in files))},
        "middleware": await middleware_probe(), "dependency": await dependency_probe(),
        "cors": await cors_probe(), "decode_errors": decode_probe(),
        "lazy_documentation": await docs_probe(),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
