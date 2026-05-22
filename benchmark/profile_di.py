"""Micro-bench for the DI resolver hot path.

Compares DependencyResolver.resolve_dependency across N iterations for
the three scopes (singleton, request, transient).  Used by Phase 2 of the
v1.2.9 Cython sprint to confirm the cdef-class migration actually helps
DI-heavy endpoints.
"""

import asyncio
import time

from tachyon_api import Tachyon, injectable
from tachyon_api.processing.dependencies import DependencyResolver

N = 200_000


@injectable
class SingletonDep:
    def __init__(self):
        self.value = 42


@injectable(scope="request")
class RequestDep:
    def __init__(self):
        self.value = "request-scoped"


@injectable(scope="transient")
class TransientDep:
    def __init__(self):
        self._seq = 0


def _bench(label: str, fn, n: int) -> None:
    t0 = time.perf_counter()
    fn(n)
    elapsed = time.perf_counter() - t0
    per_iter_us = elapsed / n * 1_000_000
    qps = n / elapsed
    print(f"  {label:50s} {per_iter_us:6.3f} µs/iter   {qps:>10,.0f} iter/s")


async def main():
    app = Tachyon()
    resolver = DependencyResolver(app)

    # Pre-warm: first resolve populates the cache
    resolver.resolve_dependency(SingletonDep)

    print("═" * 80)
    print("  DI RESOLVER MICRO-BENCH (cdef classes — Phase 2 of v1.2.9)")
    print("═" * 80)

    def run_singleton(n):
        for _ in range(n):
            resolver.resolve_dependency(SingletonDep)

    def run_request(n):
        for _ in range(n):
            cache = {}
            resolver.resolve_dependency(RequestDep, cache)

    def run_transient(n):
        for _ in range(n):
            resolver.resolve_dependency(TransientDep)

    _bench("resolve_dependency — singleton (cache hit)", run_singleton, N)
    _bench("resolve_dependency — request (fresh cache)", run_request, N)
    _bench("resolve_dependency — transient (always new)", run_transient, N)

    print("═" * 80 + "\n")


asyncio.run(main())
