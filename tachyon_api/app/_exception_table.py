# Exception handler lookup for the Python implementation.
# Registers user exception handlers and dispatches an exception to its handler.

from starlette._utils import is_async_callable
from starlette.concurrency import run_in_threadpool
import logging
from typing import Callable, Dict, Optional, Type

from starlette.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..exceptions import HTTPException
from ..processing._body_errors import RequestBodyTooLarge
from ..responses import validation_error_response, internal_server_error_response

logger = logging.getLogger(__name__)


class ExceptionTable:
    """Registers and dispatches user exception handlers."""

    __slots__ = ("_handlers",)

    def __init__(self) -> None:
        self._handlers: Dict[Type[Exception], Callable] = {}

    def register(self, exc_class: Type[Exception], func: Callable) -> None:
        self._handlers[exc_class] = func

    async def dispatch(self, exc: Exception, request) -> Optional[Response]:
        """Find a handler for exc and invoke it. Returns None if no handler matched.

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
    async def _invoke(handler: Callable, request, exc: Exception) -> Response:
        if is_async_callable(handler):
            return await handler(request, exc)
        return await run_in_threadpool(handler, request, exc)

    @staticmethod
    def _http_exception_response(exc: HTTPException) -> Response:
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        if exc.headers:
            for key, value in exc.headers.items():
                response.headers[key] = value
        return response
