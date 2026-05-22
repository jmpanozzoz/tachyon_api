# Cold path — 422/500 responses for request/response validation failures.

import logging
from typing import Optional

from ._json_response import TachyonJSONResponse

logger = logging.getLogger(__name__)


def validation_error_response(
    error: str = "Validation failed", errors: Optional[dict] = None
) -> TachyonJSONResponse:
    """Return a 422 with optional per-field errors."""
    body = {"success": False, "error": error, "code": "VALIDATION_ERROR"}
    if errors:
        body["errors"] = errors
    return TachyonJSONResponse(body, status_code=422)


def response_validation_error_response(
    error: str = "Response validation error",
) -> TachyonJSONResponse:
    """Return a generic 500 — internal details are logged at WARNING only."""
    logger.warning("Response validation error: %s", error)
    return TachyonJSONResponse(
        {
            "success": False,
            "error": "Internal Server Error",
            "code": "RESPONSE_VALIDATION_ERROR",
        },
        status_code=500,
    )
