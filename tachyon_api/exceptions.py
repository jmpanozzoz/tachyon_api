"""
Tachyon Exceptions Module

Provides HTTP exception classes for clean error handling in endpoints.
"""

from typing import Any, Dict, Optional


class HTTPException(Exception):
    """
    HTTP exception that can be raised in endpoints to return HTTP error responses.

    Similar to FastAPI's HTTPException, this allows endpoints to abort request
    processing and return a specific HTTP status code with a detail message.

    Attributes:
        status_code: The HTTP status code for the response
        detail: A human-readable error message
        headers: Optional dictionary of headers to include in the response

    Example:
        @app.get("/items/{item_id}")
        def get_item(item_id: int):
            if item_id not in items:
                raise HTTPException(status_code=404, detail="Item not found")
            return items[item_id]
    """

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
