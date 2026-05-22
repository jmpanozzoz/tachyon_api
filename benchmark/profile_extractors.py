"""Micro-bench for the atomic parameter extractors.

Used by Phase 4a of the v1.2.9 sprint to confirm cdef-class compilation
helps the extractor methods.  Tests the 5 "easy" extractors first
(header, cookie, query scalar, path scalar, missing helper).
"""

import time

from tachyon_api.processing._extractors.cookie import CookieExtractor
from tachyon_api.processing._extractors.header import HeaderExtractor
from tachyon_api.processing._extractors.path import PathExtractor
from tachyon_api.processing._extractors.query import QueryExtractor
from tachyon_api.processing.compiler import KIND_HEADER, KIND_COOKIE, KIND_PATH, KIND_QUERY, ParamDescriptor


N = 500_000


# ── Mock request / param-source objects ───────────────────────────────────────

class _FakeHeaders:
    def __init__(self, d): self._d = d
    def get(self, k, default=None): return self._d.get(k, default)


class _FakeCookies:
    def __init__(self, d): self._d = d
    def get(self, k, default=None): return self._d.get(k, default)


class _FakeRequest:
    def __init__(self, headers=None, cookies=None):
        self.headers = _FakeHeaders(headers or {})
        self.cookies = _FakeCookies(cookies or {})


def _bench(label, fn, n):
    t0 = time.perf_counter()
    fn(n)
    elapsed = time.perf_counter() - t0
    us = elapsed / n * 1_000_000
    print(f"  {label:50s} {us:6.3f} µs/iter   {n/elapsed:>10,.0f} iter/s")


def main():
    print("═" * 80)
    print("  EXTRACTOR MICRO-BENCH (Phase 4a of v1.2.9)")
    print("═" * 80)

    # HeaderExtractor
    header_ext = HeaderExtractor()
    header_p = ParamDescriptor(name="x_token", kind=KIND_HEADER, effective_name="x-token")
    req_with_header = _FakeRequest(headers={"x-token": "abc"})

    def run_header(n):
        for _ in range(n):
            header_ext.extract(header_p, req_with_header)

    _bench("HeaderExtractor.extract — hit", run_header, N)

    # CookieExtractor
    cookie_ext = CookieExtractor()
    cookie_p = ParamDescriptor(name="session", kind=KIND_COOKIE, effective_name="session")
    req_with_cookie = _FakeRequest(cookies={"session": "s123"})

    def run_cookie(n):
        for _ in range(n):
            cookie_ext.extract(cookie_p, req_with_cookie)

    _bench("CookieExtractor.extract — hit", run_cookie, N)

    # QueryExtractor (scalar str)
    query_ext = QueryExtractor()
    query_p = ParamDescriptor(name="q", kind=KIND_QUERY, base_type=str)

    def run_query(n):
        params = {"q": "hello"}
        for _ in range(n):
            query_ext.extract(query_p, params)

    _bench("QueryExtractor.extract — string hit", run_query, N)

    # PathExtractor (str)
    path_ext = PathExtractor()
    path_p = ParamDescriptor(name="id", kind=KIND_PATH, base_type=str)

    def run_path(n):
        params = {"id": "abc123"}
        for _ in range(n):
            path_ext.extract(path_p, params)

    _bench("PathExtractor.extract — string hit", run_path, N)

    # PathExtractor (int — exercises TypeConverter)
    path_int_p = ParamDescriptor(name="id", kind=KIND_PATH, base_type=int)

    def run_path_int(n):
        params = {"id": "42"}
        for _ in range(n):
            path_ext.extract(path_int_p, params)

    _bench("PathExtractor.extract — int conversion", run_path_int, N)

    print("═" * 80 + "\n")


main()
