# Cold path — convenience helpers for `{"success": False, ...}` responses.

from typing import Optional

from ._json_response import TachyonJSONResponse


def error_response(
    error: str, status_code: int = 400, code: Optional[str] = None
) -> TachyonJSONResponse:
    """Return a structured error response body."""
    body = {"success": False, "error": error}
    if code:
        body["code"] = code
    return TachyonJSONResponse(body, status_code)


def not_found_response(error: str = "Resource not found") -> TachyonJSONResponse:
    """Return a 404 with `code=NOT_FOUND`."""
    return error_response(error, status_code=404, code="NOT_FOUND")


def conflict_response(error: str = "Resource conflict") -> TachyonJSONResponse:
    """Return a 409 with `code=CONFLICT`."""
    return error_response(error, status_code=409, code="CONFLICT")
