# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled bytes response.

Sibling of `_bytes_response.py`. Compiled as a regular Python class
(see `_json_response.pyx` for why `cdef class` is not viable).
"""

from starlette.responses import JSONResponse

from ._caches import _CL_TUPLE_CACHE, _CT_TUPLE
from ._constants import _ASGI_BODY, _ASGI_START, _CL_NAME


class TachyonBytesResponse(JSONResponse):
    """JSON response that accepts pre-encoded bytes — no re-serialization."""

    __slots__ = ("_send_start", "_send_body")

    media_type = "application/json"

    def __init__(self, body: bytes, status_code: int = 200):
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

    async def __call__(self, scope, receive, send) -> None:
        await send(self._send_start)
        await send(self._send_body)
