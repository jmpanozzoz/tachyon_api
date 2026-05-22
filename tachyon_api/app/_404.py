# HOT PATH — Pre-built 404 ASGI messages.
# MappingProxyType makes the dicts read-only to defend against non-compliant
# ASGI servers that might mutate them.

import types as _types

_404_BODY = b"Not Found"
_404_HEADERS = [
    (b"content-length", b"9"),
    (b"content-type", b"text/plain; charset=utf-8"),
]
_404_START = _types.MappingProxyType(
    {"type": "http.response.start", "status": 404, "headers": _404_HEADERS}
)
_404_BODY_MSG = _types.MappingProxyType(
    {"type": "http.response.body", "body": _404_BODY}
)
