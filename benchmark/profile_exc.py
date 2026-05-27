"""Micro-bench for the ExceptionTable dispatch hot path.

Used by Phase 3 of the v1.2.9 Cython sprint to confirm the cdef-class
migration actually helps endpoints that raise.  `dispatch` is async, so
each iteration goes through one `await` cycle.
"""

import asyncio
import time

from starlette.responses import JSONResponse

from tachyon_api import HTTPException
from tachyon_api.app._exception_table import ExceptionTable


N = 200_000


class _DomainError(HTTPException):
    def __init__(self, detail):
        super().__init__(status_code=418, detail=detail)
        self.error_code = "TEAPOT"


async def _domain_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.error_code, "detail": exc.detail},
    )


async def _bench(label: str, coro_fn, n: int) -> None:
    t0 = time.perf_counter()
    await coro_fn(n)
    elapsed = time.perf_counter() - t0
    per_iter_us = elapsed / n * 1_000_000
    print(f"  {label:55s} {per_iter_us:6.3f} µs/iter   {n/elapsed:>10,.0f} iter/s")


async def main():
    table = ExceptionTable()
    table.register(_DomainError, _domain_handler)

    domain_exc = _DomainError("boom")
    plain_http = HTTPException(status_code=404, detail="missing")
    request = object()

    print("═" * 85)
    print("  ExceptionTable.dispatch MICRO-BENCH (cdef class — Phase 3 of v1.2.9)")
    print("═" * 85)

    async def dispatch_registered(n):
        for _ in range(n):
            await table.dispatch(domain_exc, request)

    async def dispatch_default_http(n):
        for _ in range(n):
            await table.dispatch(plain_http, request)

    await _bench("dispatch — handler match (subclass)", dispatch_registered, N)
    await _bench("dispatch — default HTTPException body (no match)", dispatch_default_http, N)

    print("═" * 85 + "\n")


asyncio.run(main())
