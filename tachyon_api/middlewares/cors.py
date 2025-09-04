from typing import Iterable, Optional, Sequence, Tuple


class CORSMiddleware:
    """
    ASGI middleware for handling CORS.

    Parameters:
    - allow_origins: list of allowed origins (e.g., ["https://foo.com", "*"])
    - allow_methods: list of allowed methods (default ["*"])
    - allow_headers: list of allowed headers (default ["*"])
    - allow_credentials: if True, adds Access-Control-Allow-Credentials: true
    - expose_headers: list of headers to expose to the client app
    - max_age: seconds to cache the preflight response

    Behavior:
    - If it's a preflight (OPTIONS + Access-Control-Request-Method), responds 200 with
      the appropriate CORS headers.
    - For normal requests, injects CORS headers into the response.
    """

    def __init__(
        self,
        app,
        allow_origins: Iterable[str] = ("*",),
        allow_methods: Iterable[str] = ("*",),
        allow_headers: Iterable[str] = ("*",),
        allow_credentials: bool = False,
        expose_headers: Iterable[str] = (),
        max_age: int = 600,
    ):
        self.app = app
        self.allow_origins = [o for o in allow_origins]
        self.allow_methods = [m.upper() for m in allow_methods]
        self.allow_headers = [h for h in allow_headers]
        self.allow_credentials = allow_credentials
        self.expose_headers = [h for h in expose_headers]
        self.max_age = max_age

    @staticmethod
    def _get_header(headers: Sequence[Tuple[bytes, bytes]], name: str) -> Optional[str]:
        # Find a header in a case-insensitive manner and decode it
        lower = name.lower().encode()
        for k, v in headers or []:
            if k.lower() == lower:
                try:
                    return v.decode()
                except Exception:
                    return None
        return None

    @staticmethod
    def _append_header(headers: list[Tuple[bytes, bytes]], name: str, value: str):
        # Append header encoded as bytes as required by ASGI
        headers.append((name.encode(), value.encode()))

    def _origin_allowed(self, origin: Optional[str]) -> bool:
        if origin is None:
            return False
        if "*" in self.allow_origins:
            return True
        return origin in self.allow_origins

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        req_headers: Sequence[Tuple[bytes, bytes]] = scope.get("headers", []) or []
        origin = self._get_header(req_headers, "origin")
        method = scope.get("method", "").upper()
        is_preflight = (
            method == "OPTIONS"
            and self._get_header(req_headers, "access-control-request-method")
            is not None
        )

        # Build common CORS headers
        def build_cors_headers() -> list[Tuple[bytes, bytes]]:
            headers_out: list[Tuple[bytes, bytes]] = []
            if not self._origin_allowed(origin):
                return headers_out

            # Access-Control-Allow-Origin
            if "*" in self.allow_origins and not self.allow_credentials:
                self._append_header(headers_out, "access-control-allow-origin", "*")
            else:
                self._append_header(headers_out, "access-control-allow-origin", origin)
                # Necessary for proxies/caches when echoing the origin
                self._append_header(headers_out, "vary", "Origin")

            # Credentials
            if self.allow_credentials:
                self._append_header(
                    headers_out, "access-control-allow-credentials", "true"
                )

            return headers_out

        # Handle preflight
        if is_preflight:
            resp_headers = build_cors_headers()
            if resp_headers:
                # Methods
                allow_methods = (
                    ", ".join(self.allow_methods)
                    if "*" not in self.allow_methods
                    else "*"
                )
                self._append_header(
                    resp_headers, "access-control-allow-methods", allow_methods
                )

                # Requested headers or wildcard
                req_acrh = self._get_header(
                    req_headers, "access-control-request-headers"
                )
                if "*" in self.allow_headers:
                    allow_headers = req_acrh or "*"
                else:
                    allow_headers = ", ".join(self.allow_headers)
                if allow_headers:
                    self._append_header(
                        resp_headers, "access-control-allow-headers", allow_headers
                    )

                # Max-Age
                if self.max_age:
                    self._append_header(
                        resp_headers, "access-control-max-age", str(self.max_age)
                    )

                # Respond directly
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": resp_headers,
                    }
                )
                await send({"type": "http.response.body", "body": b""})
                return
            # If origin not allowed, continue the chain (app will respond accordingly)

        # Normal requests: inject CORS headers into the response
        cors_headers = build_cors_headers()

        # Expose-Headers
        if cors_headers and self.expose_headers:
            expose = ", ".join(self.expose_headers)
            self._append_header(cors_headers, "access-control-expose-headers", expose)

        async def send_wrapper(message):
            if message.get("type") == "http.response.start" and cors_headers:
                headers = list(message.get("headers", []) or [])
                headers.extend(cors_headers)
                message["headers"] = headers
            return await send(message)

        return await self.app(scope, receive, send_wrapper)
