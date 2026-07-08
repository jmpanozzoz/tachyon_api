"""
Time the actual Tachyon hot path in-process without network overhead.
Measures each layer independently.
"""
import asyncio
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, AsyncMock


async def make_mock_request(path: str, method: str = "GET",
                             body: bytes = b"", query: str = ""):
    from tachyon_api.processing.scope import TachyonScope
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query.encode(),
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
        "path_params": {},
        "app": None,
    }
    receive = AsyncMock(return_value={"type": "http.request", "body": body, "more_body": False})
    req = TachyonScope(scope, receive, None)
    # Pre-warm the body cache so profiling measures processing not I/O
    if body:
        await req.body()
    return req


ITERATIONS = 50_000

def timed(label: str, n: int, elapsed: float):
    per_req_us = (elapsed / n) * 1_000_000
    print(f"  {label:<45} {per_req_us:>7.2f} µs/req   {n/elapsed:>10,.0f} req/s")


async def main():
    from tachyon_api import Tachyon, Struct
    from tachyon_api.params import Body, Query
    from tachyon_api.processing.compiler import compile_endpoint
    from tachyon_api.processing.parameters import ParameterProcessor
    from tachyon_api.processing.response_processor import ResponseProcessor

    app = Tachyon()

    class Item(Struct):
        name: str
        price: float

    @app.get("/hello")
    def hello():
        return {"message": "Hello, World!"}

    @app.get("/items/{item_id}")
    def get_item(item_id: int, q: str = Query(None)):
        return {"item_id": item_id, "q": q}

    @app.post("/items")
    def create_item(item: Item = Body()):
        return {"name": item.name}

    compiled_hello   = compile_endpoint(hello, "/hello")
    compiled_item    = compile_endpoint(get_item, "/items/{item_id}")
    compiled_body    = compile_endpoint(create_item, "/items")

    proc   = ParameterProcessor(app)
    req_hello  = await make_mock_request("/hello")
    req_item   = await make_mock_request("/items/42", query="q=test")
    req_item._scope["path_params"] = {"item_id": "42"}
    req_body   = await make_mock_request("/items", "POST", b'{"name":"Widget","price":9.99}')

    print("\n" + "═"*65)
    print("  TACHYON HOT PATH MICRO-BENCHMARKS")
    print("═"*65)

    # ── 1. compile_endpoint (should be one-time, but measure anyway) ──
    N = 10_000
    t0 = time.perf_counter()
    from tachyon_api.processing.compiler import _COMPILED
    for _ in range(N):
        _COMPILED.get(hello)  # simulate cache lookup
    timed("compile_endpoint cache lookup", N, time.perf_counter() - t0)

    # ── 2. process_parameters — hello (no params) ──
    N = ITERATIONS
    dep_cache = {}
    t0 = time.perf_counter()
    for _ in range(N):
        kwargs, err, bg = await proc.process_parameters(compiled_hello, req_hello, dep_cache)
    timed("process_parameters — no params", N, time.perf_counter() - t0)

    # ── 3. process_parameters — path + query ──
    dep_cache = {}
    t0 = time.perf_counter()
    for _ in range(N):
        kwargs, err, bg = await proc.process_parameters(compiled_item, req_item, dep_cache)
    timed("process_parameters — path+query", N, time.perf_counter() - t0)

    # ── 4. process_parameters — body ──
    dep_cache = {}
    t0 = time.perf_counter()
    for _ in range(N):
        kwargs, err, bg = await proc.process_parameters(compiled_body, req_body, dep_cache)
    timed("process_parameters — body POST", N, time.perf_counter() - t0)

    # ── 5. call_endpoint (sync) ──
    args_hello = []   # F7: list instead of dict
    t0 = time.perf_counter()
    for _ in range(N):
        payload = await ResponseProcessor.call_endpoint(compiled_hello, args_hello)
    timed("call_endpoint — sync", N, time.perf_counter() - t0)

    # ── 6. process_response — dict ──
    payload_dict = {"message": "Hello, World!"}
    t0 = time.perf_counter()
    for _ in range(N):
        resp = await ResponseProcessor.process_response(payload_dict, None, None)
    timed("process_response — dict payload", N, time.perf_counter() - t0)

    # ── 7. process_response — Struct ──
    payload_struct = Item(name="x", price=1.0)
    t0 = time.perf_counter()
    for _ in range(N):
        resp = await ResponseProcessor.process_response(payload_struct, None, None)
    timed("process_response — Struct payload", N, time.perf_counter() - t0)

    # ── 8. TachyonJSONResponse render ──
    from tachyon_api.responses import TachyonJSONResponse
    t0 = time.perf_counter()
    for _ in range(N):
        r = TachyonJSONResponse(payload_dict)
    timed("TachyonJSONResponse(dict)", N, time.perf_counter() - t0)

    # ── 9. msgspec.json.encode Struct directly ──
    import msgspec
    t0 = time.perf_counter()
    for _ in range(N):
        b = msgspec.json.encode(payload_struct)
    timed("msgspec.json.encode(Struct)", N, time.perf_counter() - t0)

    # ── 10. orjson.dumps dict ──
    import orjson
    t0 = time.perf_counter()
    for _ in range(N):
        b = orjson.dumps(payload_dict)
    timed("orjson.dumps(dict)", N, time.perf_counter() - t0)

    # ── 11. starlette Response(bytes) ──
    from starlette.responses import Response
    content_bytes = b'{"message":"Hello, World!"}'
    t0 = time.perf_counter()
    for _ in range(N):
        r = Response(content=content_bytes, media_type="application/json")
    timed("starlette.Response(bytes)", N, time.perf_counter() - t0)

    # ── 12. Full handler round-trip (our code only, no network) ──
    t0 = time.perf_counter()
    dep_cache = {}
    for _ in range(N):
        args, err, bg = await proc.process_parameters(compiled_hello, req_hello, dep_cache)
        payload = await ResponseProcessor.call_endpoint(compiled_hello, args)
        resp = await ResponseProcessor.process_response(payload, None, bg)
    timed("FULL HANDLER (no network, no routing)", N, time.perf_counter() - t0)

    print("═"*65 + "\n")


asyncio.run(main())
