# HOT PATH — builds the per-request ASGI closure for endpoints with NO params and
# NO callable deps.  Skips Request() creation entirely; calls endpoint with [].
#
# When running under TachyonServer, the closure detects the _tachyon_cycle on
# the scope and uses a single transport.write() instead of two await send() calls.

from typing import Callable, Optional, Type

from starlette.requests import Request

from ..exceptions import HTTPException
from ..processing.compiler import CompiledEndpoint
from ..processing.response_processor import ResponseProcessor
from ..responses import TachyonBytesResponse, TachyonJSONResponse, internal_server_error_response
from ..server import tachyon_direct_write as _tachyon_direct_write


class FastASGIFactory:
    """Builds the no-param fast-path ASGI handler closure."""

    __slots__ = ("_app",)

    def __init__(self, app) -> None:
        self._app = app

    def build(
        self,
        compiled: CompiledEndpoint,
        response_model: Optional[Type],
    ) -> Callable:
        _compiled = compiled
        _response_model = response_model
        _app = self._app

        async def _fast_asgi(scope, receive, send) -> None:
            try:
                payload = await ResponseProcessor.call_endpoint(_compiled, [])
                resp = await ResponseProcessor.process_response(payload, _response_model, None)

                if type(resp) is TachyonBytesResponse or type(resp) is TachyonJSONResponse:
                    cycle = scope.get("_tachyon_cycle")
                    if cycle is not None and _tachyon_direct_write(cycle, resp):
                        return
                    await send(resp._send_start)
                    await send(resp._send_body)
                else:
                    await resp(scope, receive, send)

            except HTTPException as exc:
                resp = await _app._exc_table.dispatch(exc, Request(scope, receive, send))
                if resp is None:
                    resp = internal_server_error_response()
                await resp(scope, receive, send)

            except Exception as exc:
                resp = await _app._exc_table.dispatch(exc, Request(scope, receive, send))
                if resp is None:
                    resp = internal_server_error_response()
                await resp(scope, receive, send)

        return _fast_asgi
