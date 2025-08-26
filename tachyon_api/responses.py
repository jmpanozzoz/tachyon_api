"""
Simple response helpers for Tachyon API

Provides convenient response helpers while keeping full compatibility
with Starlette responses.
"""

from starlette.responses import JSONResponse, HTMLResponse  # noqa
import orjson
from .models import encode_json


class TachyonJSONResponse(JSONResponse):
    """High-performance JSON response using orjson for serialization."""

    media_type = "application/json"

    def render(self, content) -> bytes:  # type: ignore[override]
        # Use centralized encoder to support Struct, UUID, date, datetime, etc.
        return encode_json(content)


# Simple helper functions for common response patterns
def success_response(data=None, message="Success", status_code=200):
    """Create a success response with consistent structure"""
    return TachyonJSONResponse(
        {"success": True, "message": message, "data": data}, status_code=status_code
    )


def error_response(error, status_code=400, code=None):
    """Create an error response with consistent structure"""
    response_data = {"success": False, "error": error}
    if code:
        response_data["code"] = code

    return TachyonJSONResponse(response_data, status_code=status_code)


def not_found_response(error="Resource not found"):
    """Create a 404 not found response"""
    return error_response(error, status_code=404, code="NOT_FOUND")


def conflict_response(error="Resource conflict"):
    """Create a 409 conflict response"""
    return error_response(error, status_code=409, code="CONFLICT")


def validation_error_response(error="Validation failed", errors=None):
    """Create a 422 validation error response"""
    response_data = {"success": False, "error": error, "code": "VALIDATION_ERROR"}
    if errors:
        response_data["errors"] = errors

    return TachyonJSONResponse(response_data, status_code=422)


def response_validation_error_response(error="Response validation error"):
    """Create a 500 response validation error response"""
    # Normalize message with prefix and include 'detail' for backward compatibility
    msg = str(error)
    if not msg.lower().startswith("response validation error"):
        msg = f"Response validation error: {msg}"
    return TachyonJSONResponse(
        {"success": False, "error": msg, "detail": msg, "code": "RESPONSE_VALIDATION_ERROR"},
        status_code=500,
    )


# Re-export Starlette responses for convenience
# JSONResponse is already imported above
# HTMLResponse is now also imported
