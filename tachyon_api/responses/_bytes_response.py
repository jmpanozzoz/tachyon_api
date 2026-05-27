# HOT PATH — cdef migration target for v1.3.x.
# Like TachyonJSONResponse but accepts pre-encoded bytes (msgspec output).

from starlette.responses import JSONResponse

from ._caches import _CL_TUPLE_CACHE, _CT_TUPLE
from ._constants import _ASGI_BODY, _ASGI_START, _CL_NAME


class TachyonBytesResponse(JSONResponse):
    """JSON response that accepts pre-encoded bytes — no re-serialization."""

    __slots__ = ("_send_start", "_send_body")  # → cdef object on migration

    media_type = "application/json"

    def __init__(self, body: bytes, status_code: int = 200):
        n = len(body)
        headers = [
            _CL_TUPLE_CACHE[n] if n < 65536 else (_CL_NAME, str(n).encode()),
            _CT_TUPLE,
        ]
        self.body = body
        self.status_code = status_code
        self.background = None
        self.raw_headers = headers
        self._send_start = {"type": _ASGI_START, "status": status_code, "headers": headers}
        self._send_body = {"type": _ASGI_BODY, "body": body}

    async def __call__(self, scope, receive, send) -> None:
        await send(self._send_start)
        await send(self._send_body)
