# HOT PATH — precomputed lookup tables for response-header construction.
#
# `_CL_CACHE` and `_CL_TUPLE_CACHE` cover content-length values 0–65535 (~64KB),
# the practical limit for JSON API responses. Build cost is ~512KB of memory
# at import time; per-request cost is one dict lookup instead of
# `str(n).encode()` (≈70ns) plus tuple allocation (≈20ns).

from ._constants import _CL_NAME, _CT_JSON, _CT_NAME

_CL_CACHE: dict = {i: str(i).encode() for i in range(65536)}


def _cl_bytes(n: int) -> bytes:
    """Return pre-encoded bytes for content-length value n (fallback if n ≥ 65536)."""
    cached = _CL_CACHE.get(n)
    return cached if cached is not None else str(n).encode()


# Singleton — every JSON response uses this exact tuple.
_CT_TUPLE: tuple = (_CT_NAME, _CT_JSON)

# Pre-built (content-length, value) tuples for the common cases.
_CL_TUPLE_CACHE: dict = {n: (_CL_NAME, _cl_bytes(n)) for n in range(65536)}


def _cl_tuple(n: int) -> tuple:
    """Return cached (b'content-length', encoded_n) tuple."""
    t = _CL_TUPLE_CACHE.get(n)
    return t if t is not None else (_CL_NAME, str(n).encode())
