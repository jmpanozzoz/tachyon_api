"""
Simple response helpers for Tachyon API

Provides convenient response helpers while keeping full compatibility
with Starlette responses.
"""

from starlette.responses import JSONResponse, HTMLResponse


# Simple helper functions for common response patterns
def success_response(data=None, message="Success", status_code=200):
    """Create a success response with consistent structure"""
    return JSONResponse(
        {"success": True, "message": message, "data": data}, status_code=status_code
    )


def error_response(error, status_code=400, code=None):
    """Create an error response with consistent structure"""
    response_data = {"success": False, "error": error}
    if code:
        response_data["code"] = code

    return JSONResponse(response_data, status_code=status_code)


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

    return JSONResponse(response_data, status_code=422)


# Re-export Starlette responses for convenience
