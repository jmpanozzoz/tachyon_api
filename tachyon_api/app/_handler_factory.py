# HOT PATH — builds the per-request async closure for endpoints with parameters.
# The returned closure handles the full request lifecycle:
#   1. Allocate dependency cache (only when needed)
#   2. Extract parameters via ParameterProcessor
#   3. Invoke endpoint + process response
#   4. Delegate exceptions to ExceptionTable
#
# The factory itself is cold path (runs at route registration).
# The returned closure is hot path (runs per request).

from typing import Callable, Optional, Type

from ..exceptions import HTTPException
from ..processing.compiler import CompiledEndpoint
from ..processing.response_processor import ResponseProcessor
from ..responses import internal_server_error_response


class HandlerFactory:
    """Builds the async request handler closure for endpoints with parameters."""

    __slots__ = ("_app",)

    def __init__(self, app) -> None:
        self._app = app

    def build(
        self,
        compiled: CompiledEndpoint,
        response_model: Optional[Type],
    ) -> Callable:
        _has_params = compiled.has_params
        _has_callable_deps = compiled.has_callable_deps
        _app = self._app

        async def handler(request):
            try:
                dependency_cache = {} if _has_callable_deps else None

                if _has_params:
                    args, error_response, _bg = (
                        await _app._parameter_processor.process_parameters(
                            compiled, request, dependency_cache
                        )
                    )
                    if error_response is not None:
                        return error_response
                else:
                    args = []
                    _bg = None

                payload = await ResponseProcessor.call_endpoint(compiled, args)
                return await ResponseProcessor.process_response(
                    payload, response_model, _bg
                )

            except HTTPException as exc:
                response = await _app._exc_table.dispatch(exc, request.as_request())
                if response is not None:
                    return response
                return internal_server_error_response()

            except Exception as exc:
                response = await _app._exc_table.dispatch(exc, request.as_request())
                if response is not None:
                    return response
                return internal_server_error_response()

        return handler
