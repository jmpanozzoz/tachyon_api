# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled body extractor.

Reads the request body (size-validated) and decodes it with msgspec.
The size checker is `cimport`-ed for typed C-level dispatch.
"""

import msgspec

from ...responses import validation_error_response
from .body_limit cimport BodySizeChecker


cdef class BodyExtractor:
    """Reads request body and decodes with msgspec.json.Decoder."""

    def __init__(self, max_body_size):
        self._size_check = BodySizeChecker(max_body_size)

    async def extract(self, descriptor, request):
        """Returns `(value, error)` plain tuple."""
        err = self._size_check.check_content_length(request)
        if err is not None:
            return (None, err)

        try:
            raw_body = await request.body()
        except Exception:
            return (None, validation_error_response("Failed to read request body"))

        err = self._size_check.check_body_length(raw_body)
        if err is not None:
            return (None, err)

        return _decode(raw_body, descriptor.decoder)


cdef _decode(bytes raw_body, object decoder):
    if decoder is None:
        return (None, validation_error_response("Body type must be a Struct subclass"))
    try:
        return (decoder.decode(raw_body), None)
    except msgspec.DecodeError as e:
        return (None, validation_error_response(f"Invalid JSON body: {e}"))
    except msgspec.ValidationError as e:
        return (None, _msgspec_validation_response(e))


cdef _msgspec_validation_response(object e):
    cdef object field_errors = None
    try:
        path = getattr(e, "path", None)
        if path:
            for seg in reversed(path):
                if isinstance(seg, str):
                    field_errors = {seg: [str(e)]}
                    break
    except Exception:
        pass
    return validation_error_response(str(e), errors=field_errors)
