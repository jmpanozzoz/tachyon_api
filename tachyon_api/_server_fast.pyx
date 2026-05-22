# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-compiled tachyon_direct_write for F12b.

Key optimisations vs the Python version:

1. Default-headers cache: uvicorn's default_headers list contains (server, date).
   The Date value changes once per second. We cache the pre-joined bytes and skip
   the loop + b"".join on every request — just a pointer comparison.

2. C-typed locals: cdef bytes / cdef object / cdef bint avoid Python name-table
   lookups and let Cython generate direct C variable access.

3. Single b"".join for the header block (status + cached_defaults + CL + CT headers),
   then a second transport.write(body) — avoids copying body bytes into the join buffer.
"""

from .responses import (
    _HTTP_CL_PREFIX,
    _HTTP_CRLF,
    _HTTP_CT_JSON_CRLF2,
    _cl_bytes,
    _http_status_line,
)

# ── Default-headers cache ─────────────────────────────────────────────────────
# Updated when the Date header changes (≤ once per second at 50k+ req/s).
# At module level so it survives across requests on the same worker process.

cdef bytes _cached_default_bytes = b""
cdef bytes _cached_date_value    = b""


cdef bytes _get_default_bytes(list default_headers):
    """Return pre-joined b'name: value\\r\\n...' for uvicorn default headers."""
    global _cached_default_bytes, _cached_date_value

    # Find the Date header value — it's usually the second item
    cdef object name, value
    cdef bytes date_val = b""
    for name, value in default_headers:
        if name == b"date":
            date_val = value
            break

    # Cache hit — same Date value as last time
    if date_val is _cached_date_value or date_val == _cached_date_value:
        return _cached_default_bytes

    # Cache miss — rebuild (happens at most once per second)
    _cached_date_value = date_val
    cdef list parts = []
    for name, value in default_headers:
        parts.extend([name, b": ", value, b"\r\n"])
    _cached_default_bytes = b"".join(parts)
    return _cached_default_bytes


# ── Main function ─────────────────────────────────────────────────────────────

def tachyon_direct_write(cycle, response) -> bool:
    """
    Write HTTP response directly to transport — bypasses 2× ASGI send() awaits.

    Builds: STATUS_LINE + cached(default_headers) + content-length + content-type,
    writes the header block + body as two synchronous transport.write() calls,
    then updates the uvicorn cycle state for keep-alive / pipelining.

    Returns False when flow-controlled so caller falls back to normal send().
    """
    cdef bint write_paused = cycle.flow.write_paused
    cdef bint disconnected = cycle.disconnected

    if write_paused or disconnected:
        return False

    cdef object body       = response.body
    cdef int    status     = response.status_code
    cdef bint   keep_alive = cycle.keep_alive

    # Header bytes: STATUS + cached_defaults + CL_PREFIX + cl + CRLF + CT_CRLF2
    cdef bytes status_line    = _http_status_line(status)
    cdef bytes default_bytes  = _get_default_bytes(cycle.default_headers)
    cdef bytes cl             = _cl_bytes(len(body))

    cdef bytes header_block = (
        status_line + default_bytes
        + _HTTP_CL_PREFIX + cl + _HTTP_CRLF + _HTTP_CT_JSON_CRLF2
    )

    cdef object transport = cycle.transport
    transport.write(header_block)
    transport.write(body)

    # Mirror uvicorn's cycle state update
    cycle.response_started  = True
    cycle.response_complete = True
    cycle.message_event.set()
    if not keep_alive:
        transport.close()
    cycle.on_response()
    return True
