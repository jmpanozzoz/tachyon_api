"""
TachyonDispatcher — ASGI HTTP dispatch core.

Replaces the pure-Python _trie_dispatch method as the innermost ASGI callable
in _build_http_app.  All local state captured at construction time; per-request
path is stateless (only reads self fields + scope args).

F12a: responses are sent inline (no response.__call__ coroutine overhead).
F12b: when running under TachyonServer, a pre-built bytes message is injected
      into the scope and the server writes headers+body in a single transport call.
"""
from __future__ import annotations
from ..server import tachyon_direct_write as _tachyon_direct_write


class TachyonDispatcher:
    """
    Handles trie lookup, 404/405 responses, and handler dispatch in one callable.

    Pure-Python fallback — tachyon_api/processing/dispatch.pyx is the compiled
    version preferred when the [fast] extra is installed.
    """
    __slots__ = (
        "_trie",
        "_404_start", "_404_body",
        "_405_body", "_405_ct", "_405_cl",
        "_asgi_handler_class",
    )

    def __init__(
        self,
        trie,
        _404_start, _404_body,
        _405_body, _405_ct, _405_cl,
        asgi_handler_class,
    ):
        self._trie = trie
        self._404_start = _404_start
        self._404_body = _404_body
        self._405_body = _405_body
        self._405_ct = _405_ct
        self._405_cl = _405_cl
        self._asgi_handler_class = asgi_handler_class

    async def __call__(self, scope, receive, send) -> None:
        status, handler, path_params, allow_header = self._trie.match(
            scope["path"], scope["method"]
        )

        if status == 0:  # _NOT_FOUND
            await send(self._404_start)
            await send(self._404_body)
            return

        if status == 1:  # _METHOD_NOT_ALLOWED
            await send({
                "type": "http.response.start",
                "status": 405,
                "headers": [
                    (b"content-length", self._405_cl),
                    (b"content-type",   self._405_ct),
                    (b"allow",          allow_header.encode()),
                ],
            })
            await send({"type": "http.response.body", "body": self._405_body})
            return

        # _FOUND
        scope["path_params"] = path_params

        if type(handler) is self._asgi_handler_class:
            await handler.fn(scope, receive, send)
        else:
            from .scope import TachyonScope
            from ..responses import TachyonBytesResponse, TachyonJSONResponse
            ts = TachyonScope(scope, receive, send)
            response = await handler(ts)
            # F12a: bypass response.__call__ coroutine (~0.05µs saved)
            if type(response) is TachyonBytesResponse or type(response) is TachyonJSONResponse:
                # F12b: single transport.write() when running under TachyonServer
                cycle = scope.get("_tachyon_cycle")
                if cycle is not None and _tachyon_direct_write(cycle, response):
                    return  # done
                await send(response._send_start)
                await send(response._send_body)
            else:
                await response(scope, receive, send)
