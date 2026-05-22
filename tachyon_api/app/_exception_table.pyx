# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled exception handler dispatch table.

Sibling of `_exception_table.py`.  cdef class — registered handlers live in
a typed `_handlers` slot; dispatch walks them in insertion order and returns
the first `isinstance` match.

This module is touched per-exception (rare in the happy path).  The main
win for Phase 3 is consistency with Phase 1+2 (same compile-everything
posture), not raw latency — exception paths are not on the hot loop.
"""

import asyncio
import logging

from starlette.responses import JSONResponse, Response

from ..exceptions import HTTPException

logger = logging.getLogger(__name__)


cdef class ExceptionTable:
    """Registers and dispatches user exception handlers."""

    cdef public dict _handlers

    def __init__(self):
        self._handlers = {}

    def register(self, exc_class, func):
        if not asyncio.iscoroutinefunction(func):
            logger.warning(
                "Exception handler %r for %s is synchronous and will block the event loop. "
                "Consider making it async.",
                func.__name__,
                exc_class.__name__,
            )
        self._handlers[exc_class] = func

    async def dispatch(self, exc, request):
        """Find a handler for exc and invoke it.  Returns None if no handler matched.

        Walks registered handlers in registration order — first `isinstance`
        match wins.  This is what lets users register a handler for a
        `HTTPException` *subclass* (e.g., `MyDomainError(HTTPException)`) and
        have it invoked instead of falling through to the default
        `{"detail": ...}` response.

        If nothing matched and `exc` is an `HTTPException`, returns the
        default body.  Other unhandled exceptions return `None` and the
        caller emits a 500.
        """
        for exc_class, handler in self._handlers.items():
            if isinstance(exc, exc_class):
                return await self._invoke(handler, request, exc)

        if isinstance(exc, HTTPException):
            return self._http_exception_response(exc)
        return None

    @staticmethod
    async def _invoke(handler, request, exc):
        if asyncio.iscoroutinefunction(handler):
            return await handler(request, exc)
        return handler(request, exc)

    @staticmethod
    def _http_exception_response(exc):
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        if exc.headers:
            for key, value in exc.headers.items():
                response.headers[key] = value
        return response
