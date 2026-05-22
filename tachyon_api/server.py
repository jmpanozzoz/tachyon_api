"""
TachyonServer — custom uvicorn HTTP protocol for F12b direct transport writes.

Replaces 2× ASGI `await send()` coroutines with a single synchronous
`transport.write()` C call, eliminating:
  - 2× Python coroutine frame creation
  - 2× `await` suspension/resume overhead (~0.14µs total)
  - uvicorn's internal ASGI send() dict parsing per call

Usage:
    uvicorn.run(app, http=TachyonHTTPProtocol)
    # or
    tachyon_api.server.run(app, host="0.0.0.0", port=8000)

Falls back transparently to normal ASGI send() when:
  - TCP write buffer is full (flow control)
  - Connection is closing
  - Response type is not TachyonBytesResponse / TachyonJSONResponse
"""
from __future__ import annotations

from uvicorn.protocols.http.httptools_impl import (
    HttpToolsProtocol,
    RequestResponseCycle,
)

from .responses import (
    _HTTP_CL_PREFIX, _HTTP_CRLF, _HTTP_CT_JSON_CRLF2,
    _cl_bytes, _http_status_line,
)

# Scope key — presence signals F12b is available
_TACHYON_CYCLE_KEY = "_tachyon_cycle"


# ── Direct-write — module-level function (no closure overhead per request) ───

def tachyon_direct_write(cycle, response) -> bool:
    """
    Write pre-built HTTP response + complete the cycle, bypassing 2× ASGI send().

    STATUS_LINE + default_headers + content-length + content-type + body
    written as two synchronous transport.write() calls (header bytes + body).
    Returns False when flow-controlled — caller falls back to normal send().
    """
    if cycle.flow.write_paused or cycle.disconnected:
        return False

    # Build header bytes: status + uvicorn defaults + content-length + content-type
    parts = [_http_status_line(response.status_code)]
    for name, value in cycle.default_headers:
        parts.extend([name, b": ", value, b"\r\n"])
    parts.extend([
        _HTTP_CL_PREFIX, _cl_bytes(len(response.body)), _HTTP_CRLF, _HTTP_CT_JSON_CRLF2,
    ])
    # Two writes: header block + body (avoids copying body bytes into join)
    cycle.transport.write(b"".join(parts))
    cycle.transport.write(response.body)

    # Mirror uvicorn's state update
    cycle.response_started = True
    cycle.response_complete = True
    cycle.message_event.set()
    if not cycle.keep_alive:
        cycle.transport.close()
    cycle.on_response()
    return True


# ── Custom protocol ───────────────────────────────────────────────────────────

class TachyonHTTPProtocol(HttpToolsProtocol):
    """
    Drop-in uvicorn HTTP/1.1 protocol with F12b direct-write support.

    On each new request, injects `_tachyon_write(response) → bool` into the
    ASGI scope. TachyonDispatcher detects this key and calls it instead of
    the 2× `await send()` path when the response is a Tachyon built-in type.
    """

    def on_message_complete(self) -> None:
        super().on_message_complete()
        # Store cycle reference in scope — no closure, just a pointer
        if self.cycle and not self.cycle.response_complete:
            self.cycle.scope[_TACHYON_CYCLE_KEY] = self.cycle


# ── Convenience runner ────────────────────────────────────────────────────────

def run(app, **kwargs) -> None:
    """
    Start uvicorn with TachyonHTTPProtocol for F12b direct-write performance.

    Accepts all uvicorn.run() keyword arguments.  The `http` kwarg is overridden
    to use TachyonHTTPProtocol.

    Example::

        import tachyon_api.server as server
        server.run(app, host="0.0.0.0", port=8000, loop="uvloop", http_tools=True)
    """
    import uvicorn
    kwargs["http"] = TachyonHTTPProtocol
    uvicorn.run(app, **kwargs)
