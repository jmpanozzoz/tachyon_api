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
# Covers 0–65535 bytes (~64KB), catching JSON arrays and larger payloads.
# ~512KB startup cost for the dict; negligible vs request-time savings.
_CL_CACHE: dict = {i: str(i).encode() for i in range(65536)}


def _cl_bytes(n: int) -> bytes:
    """Return pre-cached bytes for content-length value n."""
    cached = _CL_CACHE.get(n)
    return cached if cached is not None else str(n).encode()


class TachyonJSONResponse(JSONResponse):
    """High-performance JSON response.

    Bypasses Response.__init__ (0.96µs) with direct raw_headers construction (0.27µs).
    Pre-builds both ASGI send dicts in __init__ to avoid inline dict creation in __call__.
    Overrides __call__ to skip the websocket-prefix check and background-task branch.
    """

    media_type = "application/json"

    def __init__(self, content, status_code: int = 200):
        body = encode_json(content)
        headers = [(_CL_NAME, _cl_bytes(len(body))), (_CT_NAME, _CT_JSON)]
        # Set attrs expected by Response.__call__ (kept for third-party middleware compat)
        self.body = body
        self.status_code = status_code
        self.background = None
        self.raw_headers = headers
        # Pre-built ASGI dicts — avoid inline dict creation in __call__ hot path
        self._send_start = {"type": _ASGI_START, "status": status_code, "headers": headers}
        self._send_body  = {"type": _ASGI_BODY,  "body": body}

    def render(self, content) -> bytes:
        return encode_json(content)

    async def __call__(self, scope, receive, send) -> None:
        await send(self._send_start)
        await send(self._send_body)


class TachyonBytesResponse(JSONResponse):
    """Like TachyonJSONResponse but accepts pre-encoded bytes (e.g. from msgspec)."""

    media_type = "application/json"

    def __init__(self, body: bytes, status_code: int = 200):
        headers = [(_CL_NAME, _cl_bytes(len(body))), (_CT_NAME, _CT_JSON)]
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
_INTERNAL_ERROR_HEADERS = [
    (_CL_NAME, _cl_bytes(len(_INTERNAL_ERROR_BODY))),
    (_CT_NAME, _CT_JSON),
]


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
