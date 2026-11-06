"""HTTP route dispatch through the ASGI send chain."""
from starlette._utils import get_route_path

from .scope import TachyonScope
from .response_processor import ResponseProcessor


class TachyonDispatcher:
    __slots__ = ("_trie", "_404_start", "_404_body", "_405_body", "_405_ct", "_405_cl", "_asgi_handler_class")

    def __init__(self, trie, _404_start, _404_body, _405_body, _405_ct, _405_cl, asgi_handler_class):
        self._trie = trie
        self._404_start = _404_start
        self._404_body = _404_body
        self._405_body = _405_body
        self._405_ct = _405_ct
        self._405_cl = _405_cl
        self._asgi_handler_class = asgi_handler_class

    async def __call__(self, scope, receive, send):
        status, handler, path_params, allow_header = self._trie.match(get_route_path(scope), scope["method"])
        if status == 0:
            await send({**self._404_start, "headers": list(self._404_start["headers"])})
            await send(dict(self._404_body))
            return
        if status == 1:
            await send({"type": "http.response.start", "status": 405, "headers": [
                (b"content-length", self._405_cl), (b"content-type", self._405_ct),
                (b"allow", allow_header.encode()),
            ]})
            await send({"type": "http.response.body", "body": self._405_body})
            return
        if scope.get("path_params"):
            path_params = {**scope["path_params"], **path_params}
        scope["path_params"] = path_params
        if type(handler) is self._asgi_handler_class:
            await handler.fn(scope, receive, send)
        else:
            request = TachyonScope(scope, receive, send)
            try:
                response = await handler(request)
                await ResponseProcessor.send_response(response, scope, receive, send)
            except BaseException as exc:
                request.dependency_failed(exc)
                raise
            finally:
                await request.close()
