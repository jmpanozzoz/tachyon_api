# cython: language_level=3
"""Pre-rendered error body with request-owned response containers."""

from ._bytes_response import TachyonBytesResponse

_INTERNAL_ERROR_BODY = b'{"success":false,"error":"Internal Server Error","code":"INTERNAL_SERVER_ERROR"}'


def internal_server_error_response():
    return TachyonBytesResponse(_INTERNAL_ERROR_BODY, status_code=500)
