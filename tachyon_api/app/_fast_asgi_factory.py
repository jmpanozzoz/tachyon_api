"""ASGI closures for endpoints that need no request metadata."""
from ..processing.scope import TachyonScope
from ..processing.response_processor import ResponseProcessor
from ..responses import internal_server_error_response


class FastASGIFactory:
    __slots__ = ("_app",)

    def __init__(self, app):
        self._app = app

    def build(self, compiled, response_model):
        app = self._app

        async def handler(scope, receive, send):
            request = None
            try:
                try:
                    payload = await ResponseProcessor.call_endpoint(compiled, [])
                    response = await ResponseProcessor.process_response(payload, response_model, None)
                except Exception as exc:
                    request = TachyonScope(scope, receive, send)
                    response = await app._exc_table.dispatch(exc, request.as_request())
                    if response is None:
                        response = internal_server_error_response()
                # Transmission errors must never start a second response.
                await response(scope, receive, send)
            finally:
                if request is not None:
                    await request.close()

        return handler
