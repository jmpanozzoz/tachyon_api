# HOT PATH — Pre-built 404/405 ASGI constants.
#
# 404: full start/body messages are static. MappingProxyType makes the dicts
# read-only to defend against non-compliant ASGI servers that might mutate them.
# 405: the Allow header value is computed per-route at trie registration time,
# so only the body and content-type are static.

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

_405_BODY = b"Method Not Allowed"
_405_PLAIN_CT = b"text/plain; charset=utf-8"
_CL_405 = str(len(_405_BODY)).encode()
