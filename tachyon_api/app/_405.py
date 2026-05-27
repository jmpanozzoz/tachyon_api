# HOT PATH — Pre-built 405 ASGI constants.
# The Allow header value is computed per-route at trie registration time,
# so only the body and content-type are static.

_405_BODY = b"Method Not Allowed"
_405_PLAIN_CT = b"text/plain; charset=utf-8"
_CL_405 = str(len(_405_BODY)).encode()
