"""Response classes, helpers, and ASGI/HTTP wire constants for Tachyon."""

# Re-export Starlette types (FastAPI-compatible surface)
from starlette.responses import HTMLResponse, JSONResponse, Response  # noqa: F401

# Public response classes
from ._bytes_response import TachyonBytesResponse
from ._json_response import TachyonJSONResponse

# Public helpers
from ._error import conflict_response, error_response, not_found_response
from ._internal_error import internal_server_error_response
from ._success import success_response
from ._validation import response_validation_error_response, validation_error_response

# Private symbols still consumed externally by server.py / _server_fast.pyx
# — must remain importable from `tachyon_api.responses` for the compiled .so.
from ._caches import _CL_CACHE, _CL_TUPLE_CACHE, _CT_TUPLE, _cl_bytes, _cl_tuple
from ._constants import _ASGI_BODY, _ASGI_START, _CL_NAME, _CT_JSON, _CT_NAME
from ._wire import (
    _HTTP_CL_PREFIX,
    _HTTP_CRLF,
    _HTTP_CT_JSON_CRLF2,
    _HTTP_STATUS_LINES,
    _http_status_line,
)

__all__ = [
    # Starlette re-exports
    "HTMLResponse",
    "JSONResponse",
    "Response",
    # Tachyon classes
    "TachyonJSONResponse",
    "TachyonBytesResponse",
    # Helpers
    "success_response",
    "error_response",
    "not_found_response",
    "conflict_response",
    "validation_error_response",
    "response_validation_error_response",
    "internal_server_error_response",
]
