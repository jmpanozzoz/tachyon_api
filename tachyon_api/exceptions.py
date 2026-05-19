"""HTTP exception for aborting requests with a status code and detail message."""

from typing import Any, Dict, Optional


class HTTPException(Exception):
    """Raise this inside an endpoint to return an HTTP error response."""

    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)
