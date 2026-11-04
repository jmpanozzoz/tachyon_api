# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled exception handler dispatch table.

Sibling of `_exception_table.py`.  cdef class — registered handlers live in
a typed `_handlers` slot; dispatch walks them in insertion order and returns
the first `isinstance` match.

This module is touched per-exception (rare in the happy path).  The main
win for Phase 3 is consistency with Phase 1+2 (same compile-everything
posture), not raw latency — exception paths are not on the hot loop.
"""

from starlette._utils import is_async_callable
from starlette.concurrency import run_in_threadpool
import logging

from starlette.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..exceptions import HTTPException
from ..processing._body_errors import RequestBodyTooLarge
from ..responses import validation_error_response, internal_server_error_response

logger = logging.getLogger(__name__)


cdef class ExceptionTable:
    """Registers and dispatches user exception handlers."""

    cdef public dict _handlers

    def __init__(self):
        self._handlers = {}

    def register(self, exc_class, func):
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
                try:
                    return await self._invoke(handler, request, exc)
                except RequestBodyTooLarge as limit:
                    return validation_error_response(str(limit))
                except Exception:
                    logger.exception("Exception handler %r failed", handler)
                    return internal_server_error_response()

        if isinstance(exc, RequestBodyTooLarge):
            return validation_error_response(str(exc))
        if isinstance(exc, (HTTPException, StarletteHTTPException)):
            return self._http_exception_response(exc)
        logger.error("Unhandled endpoint exception", exc_info=(type(exc), exc, exc.__traceback__))
        return None

    @staticmethod
    async def _invoke(handler, request, exc):
        if is_async_callable(handler):
            return await handler(request, exc)
        return await run_in_threadpool(handler, request, exc)

    @staticmethod
    def _http_exception_response(exc):
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        if exc.headers:
            for key, value in exc.headers.items():
                response.headers[key] = value
        return response
