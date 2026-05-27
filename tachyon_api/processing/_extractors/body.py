# HOT PATH — reads the request body and decodes it with msgspec.

from typing import Optional

import msgspec

from ..compiler import ParamDescriptor
from ..scope import TachyonScope
from ...responses import validation_error_response
from .body_limit import BodySizeChecker


class BodyExtractor:
    """Reads request body and decodes with msgspec.json.Decoder."""

    __slots__ = ("_size_check",)

    def __init__(self, max_body_size: int) -> None:
        self._size_check = BodySizeChecker(max_body_size)

    async def extract(self, descriptor: ParamDescriptor, request: TachyonScope):
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

        return self._decode(raw_body, descriptor.decoder)

    @staticmethod
    def _decode(raw_body: bytes, decoder):
        if decoder is None:
            return (None, validation_error_response("Body type must be a Struct subclass"))
        try:
            return (decoder.decode(raw_body), None)
        except msgspec.DecodeError as e:
            return (None, validation_error_response(f"Invalid JSON body: {e}"))
        except msgspec.ValidationError as e:
            return (None, _msgspec_validation_response(e))


def _msgspec_validation_response(e: msgspec.ValidationError):
    field_errors: Optional[dict] = None
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
