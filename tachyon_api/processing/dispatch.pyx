# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-compiled ASGI HTTP dispatcher.

cdef class TachyonDispatcher:
  - cdef int status       — C int, no Python int box/unbox
  - cdef object handler   — direct C pointer, no Python lookup
  - type(handler) is cls  — C type-pointer comparison (faster than isinstance)
  - All constant fields stored as cdef — direct C struct reads
"""
from .scope import TachyonScope


cdef class TachyonDispatcher:
    """
    Innermost ASGI callable for HTTP — replaces _trie_dispatch as a Cython cdef class.

    Constructed once per app, called on every HTTP request.
    Fields are C-level struct members: reads have zero Python overhead.
    """

    cdef object _trie
    cdef object _404_start
    cdef object _404_body
    cdef bytes  _405_body
    cdef bytes  _405_ct
    cdef bytes  _405_cl
    cdef type   _asgi_handler_class

    def __init__(
        self,
        trie,
        _404_start, _404_body,
        _405_body, _405_ct, _405_cl,
        asgi_handler_class,
    ):
        self._trie             = trie
        self._404_start        = _404_start
        self._404_body         = _404_body
        self._405_body         = _405_body
        self._405_ct           = _405_ct
        self._405_cl           = _405_cl
        self._asgi_handler_class = asgi_handler_class

    async def __call__(self, scope, receive, send):
        cdef int    status
        cdef object handler, path_params, allow_header

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

        # C-level type pointer comparison — faster than isinstance for exact types
        if type(handler) is self._asgi_handler_class:
            await handler.fn(scope, receive, send)
        else:
            ts = TachyonScope(scope, receive, send)
            response = await handler(ts)
            await response(scope, receive, send)
