# HOT PATH — cdef migration target for v1.3.x.
# Registers user exception handlers and dispatches an exception to its handler.

import asyncio
import logging
from typing import Callable, Dict, Optional, Type

from starlette.responses import JSONResponse, Response

from ..exceptions import HTTPException

logger = logging.getLogger(__name__)


class ExceptionTable:
    """Registers and dispatches user exception handlers."""

    __slots__ = ("_handlers",)  # Dict[Type[Exception], Callable] → cdef dict

    def __init__(self) -> None:
        self._handlers: Dict[Type[Exception], Callable] = {}

    def register(self, exc_class: Type[Exception], func: Callable) -> None:
        if not asyncio.iscoroutinefunction(func):
            logger.warning(
                "Exception handler %r for %s is synchronous and will block the event loop. "
                "Consider making it async.",
                func.__name__,
                exc_class.__name__,
            )
        self._handlers[exc_class] = func

    async def dispatch(self, exc: Exception, request) -> Optional[Response]:
        """Find a handler for exc and invoke it. Returns None if no handler matched."""
        if isinstance(exc, HTTPException):
            http_handler = self._handlers.get(HTTPException)
            if http_handler is not None:
                return await self._invoke(http_handler, request, exc)
            return self._http_exception_response(exc)

        for exc_class, handler in self._handlers.items():
            if isinstance(exc, exc_class):
                return await self._invoke(handler, request, exc)
        return None

    @staticmethod
    async def _invoke(handler: Callable, request, exc: Exception) -> Response:
        if asyncio.iscoroutinefunction(handler):
            return await handler(request, exc)
        return handler(request, exc)

    @staticmethod
    def _http_exception_response(exc: HTTPException) -> Response:
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        if exc.headers:
            for key, value in exc.headers.items():
                response.headers[key] = value
        return response
