"""Drill down into specific bottlenecks found in profile_hotpath.py."""
import asyncio
import time
import sys

N = 100_000

def t(label, n, elapsed):
    print(f"  {label:<50} {(elapsed/n)*1e6:>7.3f} µs/req")

async def main():
    import msgspec
    import orjson
    from starlette.responses import Response
    from tachyon_api.models import Struct
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
    def sync_noop(): return 1
    t0 = time.perf_counter()
    for _ in range(N):
        await noop()
    t("await async_noop()", N, time.perf_counter()-t0)

    t0 = time.perf_counter()
    for _ in range(N):
        sync_noop()
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
        d2 = {}
        d2["key"] = "val"
    t("{} + assignment", N, time.perf_counter()-t0)

    print()

def profile_router():
    """Measure route lookup separately; optionally supply a pre-change Python file."""
    import argparse
    import importlib.util
    import json
    from tachyon_api.routing.trie import RadixTrie

    parser = argparse.ArgumentParser()
    parser.add_argument("--router-only", action="store_true")
    parser.add_argument("--router-baseline")
    args = parser.parse_args()
    implementations = [("current", RadixTrie)]
    if args.router_baseline:
        spec = importlib.util.spec_from_file_location("baseline_trie", args.router_baseline)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        implementations.insert(0, ("baseline", module.RadixTrie))
    results = []
    for label, trie_type in implementations:
        trie = trie_type()
        trie.add("/hello", "GET", main)
        trie.add("/users/{id}/profile", "GET", main)
        for path in ("/hello", "/users/42/profile"):
            samples = []
            for repeat in range(5):
                start = time.perf_counter_ns()
                for _ in range(N):
                    trie.match(path, "GET")
                samples.append((time.perf_counter_ns() - start) / N)
            results.append({"implementation": label, "path": path, "ns_per_lookup": samples})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    if "--router-only" in sys.argv:
        profile_router()
    else:
        asyncio.run(main())
