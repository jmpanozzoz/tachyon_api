from typing import Iterable, Optional, Tuple


_DEFAULT_HEADERS: Tuple[Tuple[str, str], ...] = (
    ("x-content-type-options", "nosniff"),
    ("x-frame-options", "DENY"),
    ("referrer-policy", "strict-origin-when-cross-origin"),
    ("x-permitted-cross-domain-policies", "none"),
)


class SecurityHeadersMiddleware:
    """Injects security response headers on every HTTP response.

    All headers are opt-in overridable at construction time. Pass ``None`` for
    any header to remove it from the response entirely.

    Default values:
    - ``x-content-type-options: nosniff``   — prevents MIME sniffing
    - ``x-frame-options: DENY``             — prevents clickjacking
    - ``referrer-policy: strict-origin-when-cross-origin``
    - ``x-permitted-cross-domain-policies: none``

    HSTS and CSP are *not* included by default because they require site-specific
    configuration to avoid breaking TLS setups or content loading. Pass them
    explicitly if needed.

    Example::

        app.add_middleware(
            SecurityHeadersMiddleware,
            hsts="max-age=63072000; includeSubDomains",
            csp="default-src 'self'",
        )
    """

    def __init__(
        self,
        app,
        x_content_type_options: Optional[str] = "nosniff",
        x_frame_options: Optional[str] = "DENY",
        referrer_policy: Optional[str] = "strict-origin-when-cross-origin",
        x_permitted_cross_domain_policies: Optional[str] = "none",
        hsts: Optional[str] = None,
        csp: Optional[str] = None,
        extra_headers: Optional[Iterable[Tuple[str, str]]] = None,
    ):
        self.app = app
        raw: list[Tuple[bytes, bytes]] = []
        for header_name, value in (
            ("x-content-type-options", x_content_type_options),
            ("x-frame-options", x_frame_options),
            ("referrer-policy", referrer_policy),
            ("x-permitted-cross-domain-policies", x_permitted_cross_domain_policies),
            ("strict-transport-security", hsts),
            ("content-security-policy", csp),
        ):
            if value is not None:
                raw.append((header_name.encode(), value.encode()))
        if extra_headers:
            for name, val in extra_headers:
                raw.append((name.lower().encode(), val.encode()))
        # Pre-encode once at startup; list is copied per-response to avoid ASGI
        # middlewares mutating a shared reference.
        self._headers: list[Tuple[bytes, bytes]] = raw

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not self._headers:
            return await self.app(scope, receive, send)

        _headers = self._headers

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []) or [])
                headers.extend(_headers)
                message = {**message, "headers": headers}
            return await send(message)

        return await self.app(scope, receive, send_wrapper)
