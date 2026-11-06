"""Request execution, including dependencies declared on routes and routers."""
from ..processing.response_processor import ResponseProcessor
from ..responses import internal_server_error_response


class HandlerFactory:
    __slots__ = ("_app",)

    def __init__(self, app):
        self._app = app

    def build(self, compiled, response_model, dependencies=()):
        app = self._app
        needs_cache = compiled.has_callable_deps or bool(dependencies)

        async def handler(request):
            try:
                dependency_cache = {} if needs_cache else None
                for dependency in dependencies:
                    await app._dependency_resolver.resolve_callable_dependency(
                        dependency, dependency_cache, request
                    )
                args, error, background = await app._parameter_processor.process_parameters(
                    compiled, request, dependency_cache
                )
                if error is not None:
                    return error
                payload = await ResponseProcessor.call_endpoint(compiled, args)
                return await ResponseProcessor.process_response(payload, response_model, background)
            except Exception as exc:
                request.dependency_failed(exc)
                response = await app._exc_table.dispatch(exc, request.as_request())
                return response if response is not None else internal_server_error_response()

        return handler
