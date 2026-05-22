# Cold path — convenience helper for `{"success": True, ...}` responses.

from ._json_response import TachyonJSONResponse


def success_response(data=None, message: str = "Success", status_code: int = 200) -> TachyonJSONResponse:
    """Return a structured success response body."""
    return TachyonJSONResponse(
        {"success": True, "message": message, "data": data}, status_code
    )
