"""
Profile the hot path of Tachyon vs FastAPI in-process.
Runs N requests through the ASGI stack via httpx.ASGITransport.
"""
import asyncio
import cProfile
import pstats
import io
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


WARMUP   = 500
REQUESTS = 5_000

SCENARIOS = {
    "GET /hello"       : ("GET",  "/hello",            None),
    "GET /items/42"    : ("GET",  "/items/42?q=x&limit=5", None),
    "POST /items"      : ("POST", "/items",
                          b'{"name":"Widget","price":9.99,"in_stock":true}'),
    "GET /users/1"     : ("GET",  "/users/1",           None),
    "GET /users/1/di"  : ("GET",  "/users/1/profile",   None),
}


async def hit(client, method, path, body):
    headers = {}
    if body:
        headers["content-type"] = "application/json"
    r = await client.request(method, path, content=body, headers=headers)
    assert r.status_code < 500, f"{r.status_code}: {r.text}"


async def bench_app(app, label: str):
    import httpx
    transport = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )
    async with transport as client:
        print(f"\n{'─'*60}")
        print(f"  {label}")
        print(f"{'─'*60}")

        for name, (method, path, body) in SCENARIOS.items():
            # Warmup
            for _ in range(WARMUP):
                await hit(client, method, path, body)

            # Profile
            pr = cProfile.Profile()
            pr.enable()
            for _ in range(REQUESTS):
                await hit(client, method, path, body)
            pr.disable()

            # Report top 10 by cumulative time
            s = io.StringIO()
            ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
            ps.print_stats(12)
            lines = s.getvalue().split("\n")
            # Filter noise, keep our code
            interesting = [l for l in lines if any(
                x in l for x in [
                    "tachyon_api", "fastapi", "pydantic", "msgspec",
                    "orjson", "starlette", "ncalls", "cumtime", "tottime",
                    "function calls",
                ]
            )]
            print(f"\n  ▶ {name} — top functions by cumulative time:")
            print("\n".join(interesting[:20]))


async def main():
    from benchmark.app_tachyon import app as ta
    from benchmark.app_fastapi import app as fa

    await bench_app(ta, "TACHYON")
    await bench_app(fa, "FASTAPI")


asyncio.run(main())
