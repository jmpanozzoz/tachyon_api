# HOT PATH — reads the request body and decodes it with msgspec.

import msgspec

from .._body_errors import RequestBodyTooLarge

from ..compiler import ParamDescriptor
from ..scope import TachyonScope
from ...responses import validation_error_response

class BodyExtractor:
    """Reads request body and decodes with msgspec.json.Decoder."""

    __slots__ = ()

    async def extract(self, descriptor: ParamDescriptor, request: TachyonScope):
        """Returns `(value, error)` plain tuple."""
        try:
            raw_body = await request.body()
        except RequestBodyTooLarge as exc:
            return (None, validation_error_response(str(exc)))
        except Exception:
            return (None, validation_error_response("Failed to read request body"))

        return self._decode(raw_body, descriptor.decoder)

    @staticmethod
    def _decode(raw_body: bytes, decoder):
        if decoder is None:
            return (None, validation_error_response("Body type must be a Struct subclass"))
        try:
            return (decoder.decode(raw_body), None)
        except msgspec.DecodeError as e:
            return (None, validation_error_response(f"Invalid JSON body: {e}"))
