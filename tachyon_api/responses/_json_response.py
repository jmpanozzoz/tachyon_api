# HOT PATH — cdef migration target for v1.3.x.
#
# Bypasses `Response.__init__` (which costs ~0.96µs on Starlette and builds a
# MutableHeaders).  Sets attributes directly and pre-builds both ASGI send dicts
# in `__init__`, so `__call__` is two cheap `await send(...)` calls.
#
# Starlette's JSONResponse has no `__slots__`, so we can declare ours for the
# new attributes we introduce.  The parent's `body / status_code / background /
# raw_headers` continue to live in the inherited `__dict__`.

from starlette.responses import JSONResponse

from ..models import encode_json
from ._caches import _CL_TUPLE_CACHE, _CT_TUPLE
from ._constants import _ASGI_BODY, _ASGI_START, _CL_NAME


class TachyonJSONResponse(JSONResponse):
    """High-performance JSON response — builds ASGI dicts once at construction."""

    __slots__ = ("_send_start", "_send_body")  # → cdef object on migration

    media_type = "application/json"

    def __init__(self, content, status_code: int = 200):
        body = encode_json(content)
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

    def render(self, content) -> bytes:  # pragma: no cover — bypassed by our __init__
        return encode_json(content)

    async def __call__(self, scope, receive, send) -> None:
        await send(self._send_start)
        await send(self._send_body)
