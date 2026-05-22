# HOT PATH — raw HTTP/1.1 wire bytes consumed by TachyonServer's direct
# `transport.write()` path.  These constants are read by the compiled
# `_server_fast.pyx` Cython extension; renaming requires recompiling.

_HTTP_STATUS_LINES: dict = {
    200: b"HTTP/1.1 200 OK\r\n",
    201: b"HTTP/1.1 201 Created\r\n",
    204: b"HTTP/1.1 204 No Content\r\n",
    400: b"HTTP/1.1 400 Bad Request\r\n",
    401: b"HTTP/1.1 401 Unauthorized\r\n",
    403: b"HTTP/1.1 403 Forbidden\r\n",
    404: b"HTTP/1.1 404 Not Found\r\n",
    405: b"HTTP/1.1 405 Method Not Allowed\r\n",
    422: b"HTTP/1.1 422 Unprocessable Entity\r\n",
    500: b"HTTP/1.1 500 Internal Server Error\r\n",
}

_HTTP_CL_PREFIX = b"content-length: "
_HTTP_CT_JSON_CRLF2 = b"content-type: application/json\r\n\r\n"  # header + end-of-headers
_HTTP_CRLF = b"\r\n"


def _http_status_line(code: int) -> bytes:
    """Return pre-built status line bytes for the given HTTP code."""
    s = _HTTP_STATUS_LINES.get(code)
    return s if s is not None else b"HTTP/1.1 " + str(code).encode() + b" \r\n"
