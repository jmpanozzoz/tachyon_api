# Protocol-level constants — ASGI message type strings + header name/value bytes.
# Static data only, populated once at module import.

_CT_JSON = b"application/json"
_CT_NAME = b"content-type"
_CL_NAME = b"content-length"

_ASGI_START = "http.response.start"
_ASGI_BODY = "http.response.body"
