"""Response helpers and a high-performance JSON response class."""

from starlette.responses import Response, JSONResponse, HTMLResponse  # noqa: F401

import orjson
from .models import encode_json

# Pre-computed constant header bytes
_CT_JSON = b"application/json"
_CT_NAME = b"content-type"
_CL_NAME = b"content-length"


class TachyonJSONResponse(JSONResponse):
    """High-performance JSON response.

    Inherits from JSONResponse for isinstance compatibility but bypasses
    its __init__ (which costs ~0.96µs building MutableHeaders) in favour of
    direct raw_headers construction (~0.27µs).
    """

    media_type = "application/json"

    def __init__(self, content, status_code: int = 200):
        body = encode_json(content)
        # Bypass Response.__init__ — set only the attrs used by Response.__call__
        self.body = body
        self.status_code = status_code
        self.background = None
        self.raw_headers = [
            (_CL_NAME, str(len(body)).encode()),
            (_CT_NAME, _CT_JSON),
        ]

    def render(self, content) -> bytes:
        return encode_json(content)


class TachyonBytesResponse(JSONResponse):
    """Like TachyonJSONResponse but accepts pre-encoded bytes (e.g. from msgspec)."""

    media_type = "application/json"

    def __init__(self, body: bytes, status_code: int = 200):
        self.body = body
        self.status_code = status_code
        self.background = None
        self.raw_headers = [
            (_CL_NAME, str(len(body)).encode()),
            (_CT_NAME, _CT_JSON),
        ]


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
    (_CL_NAME, str(len(_INTERNAL_ERROR_BODY)).encode()),
    (_CT_NAME, _CT_JSON),
]


class _InternalErrorResponse(JSONResponse):
    """Singleton pre-rendered 500 response."""
    def __init__(self):
        self.body = _INTERNAL_ERROR_BODY
        self.status_code = 500
        self.background = None
        self.raw_headers = _INTERNAL_ERROR_HEADERS


_INTERNAL_ERROR_SINGLETON = _InternalErrorResponse()


def internal_server_error_response() -> Response:
    return _INTERNAL_ERROR_SINGLETON
