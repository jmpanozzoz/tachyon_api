"""Drill down into specific bottlenecks found in profile_hotpath.py."""
import asyncio, time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

N = 100_000

def t(label, n, elapsed):
    print(f"  {label:<50} {(elapsed/n)*1e6:>7.3f} µs/req")

async def main():
    import msgspec, orjson
    from starlette.responses import Response, JSONResponse
    from tachyon_api.responses import TachyonJSONResponse
    from tachyon_api.models import Struct, encode_json
    from tachyon_api.utils import TypeUtils, TypeConverter

    class Item(Struct):
        name: str
        price: float

    item = Item(name="Widget", price=9.99)
    d = {"message": "Hello, World!"}
    b = b'{"message":"Hello, World!"}'

    print("\n═══ Response object creation ═══════════════════════════════")

    # Baseline: what does starlette.Response really cost?
    t0 = time.perf_counter()
    for _ in range(N):
        Response(content=b, media_type="application/json")
    t("starlette.Response(bytes)", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        Response(content=b, status_code=200,
                 headers={"content-type": "application/json"})
    t("starlette.Response(bytes, explicit headers)", N, time.perf_counter()-t0)

    # Can we build a faster response?
    class FastJSON:
        __slots__ = ("body", "status_code", "raw_headers")
        def __init__(self, body: bytes, status_code: int = 200):
            self.body = body
            self.status_code = status_code
            n = str(len(body)).encode()
            self.raw_headers = [(b"content-length", n),
                                (b"content-type", b"application/json")]
        async def __call__(self, scope, receive, send):
            await send({"type":"http.response.start","status":self.status_code,
                        "headers":self.raw_headers})
            await send({"type":"http.response.body","body":self.body})

    t0 = time.perf_counter()
    for _ in range(N):
        FastJSON(b)
    t("FastJSON(bytes) — custom minimal", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        FastJSON(orjson.dumps(d))
    t("FastJSON(orjson.dumps(dict))", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        FastJSON(msgspec.json.encode(item))
    t("FastJSON(msgspec.json.encode(Struct))", N, time.perf_counter()-t0)

    print("\n═══ TypeConverter overhead ══════════════════════════════════")

    t0 = time.perf_counter()
    for _ in range(N):
        TypeConverter.convert_value("42", int, "id", is_path_param=True)
    t("convert_value('42', int, ...) current", N, time.perf_counter()-t0)

    # Would a direct int() be faster?
    t0 = time.perf_counter()
    for _ in range(N):
        int("42")
    t("int('42') bare", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        try:
            int("42")
        except (ValueError, TypeError):
            pass
    t("int('42') with try/except", N, time.perf_counter()-t0)

    # TypeUtils overhead
    t0 = time.perf_counter()
    for _ in range(N):
        TypeUtils.unwrap_optional(int)
    t("TypeUtils.unwrap_optional(int)", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        TypeUtils.unwrap_optional(str)
    t("TypeUtils.unwrap_optional(str)", N, time.perf_counter()-t0)

    print("\n═══ Serialization comparison ════════════════════════════════")

    import json
    t0 = time.perf_counter()
    for _ in range(N):
        json.dumps(d).encode()
    t("json.dumps(dict).encode()", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        orjson.dumps(d)
    t("orjson.dumps(dict)", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        msgspec.json.encode(d)
    t("msgspec.json.encode(dict)", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        msgspec.json.encode(item)
    t("msgspec.json.encode(Struct)", N, time.perf_counter()-t0)

    print("\n═══ Event loop overhead (await cost) ═══════════════════════")

    async def noop(): return 1
    t0 = time.perf_counter()
    for _ in range(N):
        await noop()
    t("await async_noop()", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        noop()  # sync call (not awaited, just measuring call overhead)
    t("call sync noop()", N, time.perf_counter()-t0)

    print("\n═══ dict creation overhead ══════════════════════════════════")

    t0 = time.perf_counter()
    for _ in range(N):
        {}
    t("{} literal", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        dict()
    t("dict()", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        d2 = {}; d2["key"] = "val"
    t("{} + assignment", N, time.perf_counter()-t0)

    print()

asyncio.run(main())
