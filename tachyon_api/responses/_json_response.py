"""JSON response with bounded header lookup and request-owned ASGI messages."""
from starlette.responses import JSONResponse

from ..models import encode_json
from ._caches import _CL_TUPLE_CACHE, _CT_TUPLE
from ._constants import _CL_NAME


class TachyonJSONResponse(JSONResponse):
    __slots__ = ()
    media_type = "application/json"

    def __init__(self, content, status_code: int = 200):
        body = encode_json(content)
        self.status_code = status_code
        self.background = None
        self.body = b"" if status_code < 200 or status_code in (204, 304) else body
        n = len(self.body)
        self.raw_headers = [_CT_TUPLE]
        if status_code >= 200 and status_code not in (204, 304):
            length_header = _CL_TUPLE_CACHE[n] if n < len(_CL_TUPLE_CACHE) else (_CL_NAME, str(n).encode())
            self.raw_headers.insert(0, length_header)

    async def __call__(self, scope, receive, send):
        await send({"type": "http.response.start", "status": self.status_code, "headers": list(self.raw_headers)})
        await send({"type": "http.response.body", "body": b"" if scope.get("method") == "HEAD" else self.body})
        if self.background is not None:
            await self.background()
