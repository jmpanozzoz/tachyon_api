import logging
import time
from typing import Optional, Sequence, Tuple


class LoggerMiddleware:
    """
    ASGI middleware for logging requests and responses.

    Options:
    - logger: logging.Logger instance (defaults to "tachyon.logger")
    - level: log level (defaults to logging.INFO)
    - include_headers: if True, log request and response headers
    - redact_headers: list of header names to redact
    - log_request_body: if True, try to read and log the request body (HTTP)

    Note: To keep it simple and non-intrusive, the body is only logged if it's
    available in a single body message (typical in tests/sync). In production,
    reading the body implies buffering receive/send, which we intentionally avoid
    here to prevent side effects.
    """

    def __init__(
        self,
        app,
        logger: Optional[logging.Logger] = None,
        level: int = logging.INFO,
        include_headers: bool = False,
        redact_headers: Optional[Sequence[str]] = None,
        log_request_body: bool = False,
    ):
        self.app = app
        self.logger = logger or logging.getLogger("tachyon.logger")
        self.level = level
        self.include_headers = include_headers
        self.redact_headers = {h.lower() for h in (redact_headers or [])}
        self.log_request_body = log_request_body

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        method: str = scope.get("method", "")
        path: str = scope.get("path", "")
        start = time.time()
        status_code_holder = {"status": None}
        response_headers_holder: list[Tuple[bytes, bytes]] = []

        # Simple, non-intrusive request body preview
        request_body_preview = None
        if self.log_request_body:
            # Non-intrusive attempt: peek the body if the first receive contains it fully
            body_chunks = []
            more_body = True

            async def recv_wrapper():
                nonlocal more_body
                message = await receive()
                if message.get("type") == "http.request":
                    body = message.get("body", b"")
                    if body:
                        body_chunks.append(body)
                    more_body = message.get("more_body", False)
                return message

            # Perform a one-time peek without fully consuming the stream
            # If body is present and more_body is False, log a small preview
            first_msg = await recv_wrapper()

            async def receive_passthrough():
                # Return the pre-received message first, then pass-through
                nonlocal first_msg
                if first_msg is not None:
                    m = first_msg
                    first_msg = None
                    return m
                return await receive()

            receive_to_use = receive_passthrough
            if body_chunks and not more_body:
                try:
                    request_body_preview = b"".join(body_chunks)[:2048].decode(
                        "utf-8", "replace"
                    )
                except Exception:
                    request_body_preview = "<non-text body>"
        else:
            receive_to_use = receive

        def _normalized_headers(headers: Sequence[Tuple[bytes, bytes]]):
            out = []
            for k, v in headers:
                name = k.decode().lower()
                if name in self.redact_headers:
                    out.append((name, "<redacted>"))
                else:
                    out.append((name, v.decode(errors="replace")))
            return out

        self.logger.log(self.level, f"--> {method} {path}")
        if self.include_headers:
            req_headers = _normalized_headers(scope.get("headers", []) or [])
            self.logger.log(self.level, f"    req headers: {req_headers}")
        if request_body_preview is not None:
            self.logger.log(self.level, f"    req body: {request_body_preview}")

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                status_code_holder["status"] = message.get("status", 0)
                response_headers_holder[:] = list(message.get("headers", []) or [])
            return await send(message)

        try:
            await self.app(scope, receive_to_use, send_wrapper)
        finally:
            duration = time.time() - start
            status = status_code_holder["status"] or 0
            self.logger.log(
                self.level, f"<-- {method} {path} {status} ({duration:.4f}s)"
            )
            if self.include_headers and response_headers_holder:
                res_headers = _normalized_headers(response_headers_holder)
                self.logger.log(self.level, f"    res headers: {res_headers}")
