"""JSON response with bounded header lookup and request-owned ASGI messages."""
from ._json_base import _JSONBytesResponse


class TachyonBytesResponse(_JSONBytesResponse):
    __slots__ = ()
