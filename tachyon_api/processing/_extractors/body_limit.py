# HOT PATH — body size validation, two-pass (header pre-flight + post-read).

from typing import Optional

from starlette.responses import JSONResponse

from ...responses import validation_error_response


class BodySizeChecker:
    """Answers: "is this request body within the configured size limit?" """

    __slots__ = ("_max",)  # int → cdef Py_ssize_t

    def __init__(self, max_body_size: int) -> None:
        self._max = max_body_size

    def check_content_length(self, request) -> Optional[JSONResponse]:
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > self._max:
                    return self._too_large_response()
            except ValueError:
                pass
        return None

    def check_body_length(self, body: bytes) -> Optional[JSONResponse]:
        if len(body) > self._max:
            return self._too_large_response()
        return None

    def _too_large_response(self) -> JSONResponse:
        return validation_error_response(
            f"Request body too large (max {self._max} bytes)"
        )
