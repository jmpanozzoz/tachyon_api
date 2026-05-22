# HOT PATH — singleton pre-rendered 500 response.
#
# The body bytes never change, so we encode them once at module import and
# reuse the same `Response` instance forever.  `internal_server_error_response()`
# always returns the same singleton.

from starlette.responses import JSONResponse, Response

from ..models import encode_json
from ._caches import _CL_TUPLE_CACHE, _CT_TUPLE
from ._constants import _ASGI_BODY, _ASGI_START, _CL_NAME

_INTERNAL_ERROR_BODY = encode_json(
    {"success": False, "error": "Internal Server Error", "code": "INTERNAL_SERVER_ERROR"}
)
_n_err = len(_INTERNAL_ERROR_BODY)
_INTERNAL_ERROR_HEADERS = [
    _CL_TUPLE_CACHE[_n_err] if _n_err < 65536 else (_CL_NAME, str(_n_err).encode()),
    _CT_TUPLE,
]
del _n_err


class _InternalErrorResponse(JSONResponse):
    """Pre-rendered 500 response — body, headers, and ASGI dicts built once."""

    __slots__ = ("_send_start", "_send_body")  # → cdef object on migration

    def __init__(self):
        self.body = _INTERNAL_ERROR_BODY
        self.status_code = 500
        self.background = None
        self.raw_headers = _INTERNAL_ERROR_HEADERS
        self._send_start = {
            "type": _ASGI_START,
            "status": 500,
            "headers": _INTERNAL_ERROR_HEADERS,
        }
        self._send_body = {"type": _ASGI_BODY, "body": _INTERNAL_ERROR_BODY}

    async def __call__(self, scope, receive, send) -> None:
        await send(self._send_start)
        await send(self._send_body)


_INTERNAL_ERROR_SINGLETON = _InternalErrorResponse()


def internal_server_error_response() -> Response:
    """Return the shared 500 response singleton."""
    return _INTERNAL_ERROR_SINGLETON
