# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled body size validation.

Two-pass: header pre-flight (`check_content_length`) + post-read
(`check_body_length`).  cdef class with cpdef methods — direct C slot
dispatch when called from body.pyx via cimport.
"""

from ...responses import validation_error_response


cdef class BodySizeChecker:
    """Answers: "is this request body within the configured size limit?" """

    def __init__(self, max_body_size):
        self._max = max_body_size

    cpdef check_content_length(self, object request):
        cdef object cl = request.headers.get("content-length")
        cdef long parsed
        if cl is not None:
            try:
                parsed = int(cl)
                if parsed > self._max:
                    return self._too_large_response()
            except ValueError:
                pass
        return None

    cpdef check_body_length(self, bytes body):
        if len(body) > self._max:
            return self._too_large_response()
        return None

    cdef inline object _too_large_response(self):
        return validation_error_response(
            f"Request body too large (max {self._max} bytes)"
        )
