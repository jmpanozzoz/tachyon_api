"""JSON response with bounded header lookup and request-owned ASGI messages."""
from ..models import encode_json
from ._json_base import _JSONBytesResponse


class TachyonJSONResponse(_JSONBytesResponse):
    __slots__ = ()

    def __init__(self, content, status_code: int = 200):
        super().__init__(encode_json(content), status_code)
