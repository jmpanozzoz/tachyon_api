# cython: language_level=3
"""
Cython-compiled TachyonScope.

cdef class: fields are C-level struct members — None checks are direct C reads
rather than Python attribute lookups through the slot descriptor protocol.
"""
from http.cookies import SimpleCookie

from starlette.datastructures import Headers, QueryParams
from starlette.requests import Request


cdef class TachyonScope:
    """Thin ASGI scope wrapper — replaces Starlette Request in the hot path."""

    cdef public object _scope
    cdef public object _receive
    cdef public object _send
    cdef object _body
    cdef object _query_params
    cdef object _headers
    cdef object _cookies
    cdef object _form_data
    cdef object _request

    def __init__(self, scope, receive, send):
        self._scope = scope
        self._receive = receive
        self._send = send
        self._body = None
        self._query_params = None
        self._headers = None
        self._cookies = None
        self._form_data = None
        self._request = None

    @property
    def path_params(self):
        return self._scope["path_params"]

    @property
    def query_params(self):
        if self._query_params is None:
            self._query_params = QueryParams(self._scope.get("query_string", b""))
        return self._query_params

    @property
    def headers(self):
        if self._headers is None:
            self._headers = Headers(scope=self._scope)
        return self._headers

    @property
    def cookies(self):
        cdef dict cookies
        if self._cookies is None:
            cookies = {}
            cookie_header = self.headers.get("cookie")
            if cookie_header:
                try:
                    sc = SimpleCookie(cookie_header)
                    for key, morsel in sc.items():
                        cookies[key] = morsel.value
                except Exception:
                    pass
            self._cookies = cookies
        return self._cookies

    async def body(self):
        cdef list chunks
        if self._body is None:
            chunks = []
            while True:
                message = await self._receive()
                chunk = message.get("body", b"")
                if chunk:
                    chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            self._body = b"".join(chunks)
        return self._body

    async def form(self):
        if self._form_data is None:
            self._form_data = await self.as_request().form()
        return self._form_data

    def as_request(self):
        if self._request is None:
            self._request = Request(self._scope, self._receive, self._send)
        return self._request
