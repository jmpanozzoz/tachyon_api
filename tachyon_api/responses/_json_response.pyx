# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled high-performance JSON response.

Sibling of `_json_response.py`. When compiled to `.so`, this version wins
the import resolution; pure-Python users fall back to the .py module,
which produces identical behavior.

**Why not `cdef class`?** Cython's `cdef class` cannot inherit from a
regular Python class like Starlette's `JSONResponse`.  Subclassing is
required by the `isinstance(x, JSONResponse)` check in
`processing/response_processor.py` (and any third-party middleware that
does the same).  We compile this module as a regular Python class — the
gain comes from method-body byte-code compilation, typed C ints for the
size check, and direct C-level dict construction.
"""

from starlette.responses import JSONResponse

from ..models import encode_json
from ._caches import _CL_TUPLE_CACHE, _CT_TUPLE
from ._constants import _ASGI_BODY, _ASGI_START, _CL_NAME


class TachyonJSONResponse(JSONResponse):
    """High-performance JSON response — builds ASGI dicts once at construction."""

    __slots__ = ("_send_start", "_send_body")

    media_type = "application/json"

    def __init__(self, content, status_code: int = 200):
        cdef bytes body = encode_json(content)
        cdef Py_ssize_t n = len(body)
        cdef object cl_tuple
        cdef list headers

        if n < 65536:
            cl_tuple = _CL_TUPLE_CACHE[n]
        else:
            cl_tuple = (_CL_NAME, str(n).encode())
        headers = [cl_tuple, _CT_TUPLE]

        self.body = body
        self.status_code = status_code
        self.background = None
        self.raw_headers = headers
        self._send_start = {"type": _ASGI_START, "status": status_code, "headers": headers}
        self._send_body = {"type": _ASGI_BODY, "body": body}

    def render(self, content) -> bytes:
        return encode_json(content)

    async def __call__(self, scope, receive, send) -> None:
        await send(self._send_start)
        await send(self._send_body)
