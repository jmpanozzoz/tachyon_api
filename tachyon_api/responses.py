"""Response helpers and a high-performance JSON response class."""

from starlette.responses import Response, JSONResponse, HTMLResponse  # noqa: F401

import orjson
from .models import encode_json

# Pre-computed constant header bytes
_CT_JSON = b"application/json"
_CT_NAME = b"content-type"
_CL_NAME = b"content-length"

# Pre-interned strings for ASGI protocol dict keys
_ASGI_START = "http.response.start"
_ASGI_BODY  = "http.response.body"

# Content-length bytes cache — avoids str(n).encode() on every response.
# Covers 0–65535 bytes (~64KB). ~512KB startup cost; negligible vs request-time savings.
_CL_CACHE: dict = {i: str(i).encode() for i in range(65536)}


def _cl_bytes(n: int) -> bytes:
    """Return pre-cached bytes for content-length value n."""
    cached = _CL_CACHE.get(n)
    return cached if cached is not None else str(n).encode()


# ── F10: pre-built header tuples ──────────────────────────────────────────────
#
# Each response currently allocates two header tuples per request:
#   (_CL_NAME, <cl_bytes>)  — varies by body size
#   (_CT_NAME, _CT_JSON)    — always identical
#
# _CT_TUPLE: module-level singleton, zero allocation per response.
# _CL_TUPLE_CACHE: 65536 pre-built (content-length, value) tuples, ~4MB startup
#   cost. Avoids one tuple allocation (~20ns) on every response whose body fits
#   in 64KB (covers >99% of JSON API responses).
#
# The headers *list* is still created fresh per response because ASGI middlewares
# (CORS, auth, etc.) may append to or replace message["headers"] in-place.
# Sharing the list would corrupt the cache when those middlewares mutate it.

_CT_TUPLE: tuple = (_CT_NAME, _CT_JSON)

_CL_TUPLE_CACHE: dict = {n: (_CL_NAME, _cl_bytes(n)) for n in range(65536)}


def _cl_tuple(n: int) -> tuple:
    """Return cached (b'content-length', encoded_n) tuple."""
    t = _CL_TUPLE_CACHE.get(n)
    return t if t is not None else (_CL_NAME, str(n).encode())


# ── F12b: pre-built HTTP/1.1 response parts for direct transport.write() ──────
#
# When running under TachyonServer, the ASGI send() coroutines are bypassed
# entirely. The server calls transport.write(status_line + default_headers + our_part)
# in a single synchronous C call — no Python coroutines, no await overhead.
#
# _http_status: b"HTTP/1.1 200 OK\r\n"  (pre-built per status code)
# _http_our_part: b"content-length: N\r\ncontent-type: application/json\r\n\r\n" + body
#
# The server prepends default_headers (server: uvicorn, date: ...) between status
# and our_part so the final wire bytes are: status + defaults + our_part.

_HTTP_STATUS_LINES: dict = {
    200: b"HTTP/1.1 200 OK\r\n",
    201: b"HTTP/1.1 201 Created\r\n",
    204: b"HTTP/1.1 204 No Content\r\n",
    400: b"HTTP/1.1 400 Bad Request\r\n",
    401: b"HTTP/1.1 401 Unauthorized\r\n",
    403: b"HTTP/1.1 403 Forbidden\r\n",
    404: b"HTTP/1.1 404 Not Found\r\n",
    405: b"HTTP/1.1 405 Method Not Allowed\r\n",
    422: b"HTTP/1.1 422 Unprocessable Entity\r\n",
    500: b"HTTP/1.1 500 Internal Server Error\r\n",
}

_HTTP_CL_PREFIX = b"content-length: "
_HTTP_CT_JSON_CRLF2 = b"content-type: application/json\r\n\r\n"  # header + end-of-headers
_HTTP_CRLF = b"\r\n"


def _http_status_line(code: int) -> bytes:
    s = _HTTP_STATUS_LINES.get(code)
    return s if s is not None else b"HTTP/1.1 " + str(code).encode() + b" \r\n"


class TachyonJSONResponse(JSONResponse):
    """High-performance JSON response.

    Bypasses Response.__init__ (0.96µs) with direct raw_headers construction (0.27µs).
    Pre-builds both ASGI send dicts in __init__ to avoid inline dict creation in __call__.
    Overrides __call__ to skip the websocket-prefix check and background-task branch.
    """

    media_type = "application/json"

    def __init__(self, content, status_code: int = 200):
        body = encode_json(content)
        n = len(body)
        headers = [_CL_TUPLE_CACHE[n] if n < 65536 else (_CL_NAME, str(n).encode()), _CT_TUPLE]
        self.body = body
        self.status_code = status_code
        self.background = None
        self.raw_headers = headers
        self._send_start = {"type": _ASGI_START, "status": status_code, "headers": headers}
        self._send_body  = {"type": _ASGI_BODY,  "body": body}

    def render(self, content) -> bytes:  # pragma: no cover — bypassed by our __init__
        return encode_json(content)

    async def __call__(self, scope, receive, send) -> None:
        await send(self._send_start)
        await send(self._send_body)


class TachyonBytesResponse(JSONResponse):
    """Like TachyonJSONResponse but accepts pre-encoded bytes (e.g. from msgspec)."""

    media_type = "application/json"

    def __init__(self, body: bytes, status_code: int = 200):
        n = len(body)
        headers = [_CL_TUPLE_CACHE[n] if n < 65536 else (_CL_NAME, str(n).encode()), _CT_TUPLE]
        self.body = body
        self.status_code = status_code
        self.background = None
        self.raw_headers = headers
        self._send_start = {"type": _ASGI_START, "status": status_code, "headers": headers}
        self._send_body  = {"type": _ASGI_BODY,  "body": body}

    async def __call__(self, scope, receive, send) -> None:
        await send(self._send_start)
        await send(self._send_body)


def success_response(data=None, message="Success", status_code=200):
    return TachyonJSONResponse(
        {"success": True, "message": message, "data": data}, status_code
    )


def error_response(error, status_code=400, code=None):
    body = {"success": False, "error": error}
    if code:
        body["code"] = code
    return TachyonJSONResponse(body, status_code)


def not_found_response(error="Resource not found"):
    return error_response(error, status_code=404, code="NOT_FOUND")


def conflict_response(error="Resource conflict"):
    return error_response(error, status_code=409, code="CONFLICT")


def validation_error_response(error="Validation failed", errors=None):
    body = {"success": False, "error": error, "code": "VALIDATION_ERROR"}
    if errors:
        body["errors"] = errors
    return TachyonJSONResponse(body, status_code=422)


def response_validation_error_response(error="Response validation error"):
    msg = str(error)
    if not msg.lower().startswith("response validation error"):
        msg = f"Response validation error: {msg}"
    return TachyonJSONResponse(
        {"success": False, "error": msg, "detail": msg, "code": "RESPONSE_VALIDATION_ERROR"},
        status_code=500,
    )


# Pre-rendered static 500 response — bytes never change
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
    """Singleton pre-rendered 500 response — body, headers, and ASGI dicts built once."""
    def __init__(self):
        self.body = _INTERNAL_ERROR_BODY
        self.status_code = 500
        self.background = None
        self.raw_headers = _INTERNAL_ERROR_HEADERS
        self._send_start = {"type": _ASGI_START, "status": 500, "headers": _INTERNAL_ERROR_HEADERS}
        self._send_body  = {"type": _ASGI_BODY,  "body": _INTERNAL_ERROR_BODY}

    async def __call__(self, scope, receive, send) -> None:
        await send(self._send_start)
        await send(self._send_body)


_INTERNAL_ERROR_SINGLETON = _InternalErrorResponse()


def internal_server_error_response() -> Response:
    return _INTERNAL_ERROR_SINGLETON
