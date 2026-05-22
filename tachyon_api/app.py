"""Core Tachyon application class."""

import asyncio
import logging
from functools import partial
from typing import Any, Dict, List, Type, Callable, Optional

logger = logging.getLogger(__name__)

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .openapi import (
    OpenAPIGenerator,
    OpenAPIConfig,
    create_openapi_config,
)
from .exceptions import HTTPException
from .middlewares.core import (
    apply_middleware_to_router,
    create_decorated_middleware_class,
)
from .responses import (
    HTMLResponse,
    internal_server_error_response,
)
from .core.lifecycle import LifecycleManager
from .core.websocket import WebSocketManager
from .processing.compiler import compile_endpoint
from .processing.parameters import ParameterProcessor
from .processing.dependencies import DependencyResolver
from .processing.response_processor import ResponseProcessor
from .routing.trie import RadixTrie, _NOT_FOUND, _METHOD_NOT_ALLOWED, _FOUND

try:
    from .cache import set_cache_config
except ImportError:  # pragma: no cover
    set_cache_config = None  # type: ignore  # pragma: no cover


# ── Pre-built 404 ASGI messages ─────────────────────────────────────────────────
# These are module-level constants. To protect against non-compliant ASGI servers
# that might mutate the dicts, we wrap them in types.MappingProxyType which raises
# TypeError on any attempted mutation.
import types as _types

_404_BODY     = b"Not Found"
_404_HEADERS  = [(b"content-length", b"9"), (b"content-type", b"text/plain; charset=utf-8")]
_404_START    = _types.MappingProxyType({"type": "http.response.start", "status": 404, "headers": _404_HEADERS})
_404_BODY_MSG = _types.MappingProxyType({"type": "http.response.body",  "body": _404_BODY})

_405_BODY     = b"Method Not Allowed"
_405_PLAIN_CT = b"text/plain; charset=utf-8"
_CL_405       = str(len(_405_BODY)).encode()


class _ASGIHandler:
    """Marks a handler that takes (scope, receive, send) directly — skips Request creation."""
    __slots__ = ("fn",)

    def __init__(self, fn: Callable) -> None:
        self.fn = fn


class Tachyon:
    def __init__(
        self,
        openapi_config: Optional[OpenAPIConfig] = None,
        cache_config: Optional[Any] = None,
        lifespan: Optional[Callable] = None,
        max_body_size: int = 10 * 1024 * 1024,
    ):
        self.max_body_size = max_body_size
        self._lifecycle_manager = LifecycleManager(lifespan)
        self._exception_handlers: Dict[Type[Exception], Callable] = {}
        self._router = Starlette(lifespan=self._lifecycle_manager.create_combined_lifespan())

        # ── Radix trie replaces Starlette's O(N) regex route scan ──
        # Starlette's Router.middleware_stack starts as Router.app (the scan loop).
        # We replace it with our dispatch *before* the first request so that
        # Starlette.build_middleware_stack() (lazy) wraps our dispatcher instead.
        self._trie = RadixTrie()
        _original_router_app = self._router.router.app  # kept for WS + lifespan
        self._router.router.middleware_stack = self._make_http_dispatch(_original_router_app)

        self._websocket_manager = WebSocketManager(self._router)
        self._parameter_processor = ParameterProcessor(self)
        self._dependency_resolver = DependencyResolver(self)
        self.routes: List[Dict[str, Any]] = []
        self.middleware_stack: List[Dict[str, Any]] = []
        self._instances_cache: Dict[Type, Any] = {}
        self.state = self._router.state
        self.dependency_overrides: Dict[Any, Any] = {}
        self.openapi_config = openapi_config or create_openapi_config()
        self.openapi_generator = OpenAPIGenerator(self.openapi_config)
        self._docs_setup = False
        self._register_common_openapi_schemas()

        self.cache_config = cache_config
        if cache_config is not None and set_cache_config is not None:
            try:
                set_cache_config(cache_config)
            except Exception as exc:
                logger.warning("Failed to apply cache config: %s", exc)

        # Lazily-built HTTP app: user middlewares → trie dispatch (no Starlette overhead)
        self._http_app: Optional[Callable] = None

        for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]:
            setattr(self, method.lower(), partial(self._create_decorator, http_method=method))

    def _register_common_openapi_schemas(self):
        self.openapi_generator.add_schema(
            "ValidationErrorResponse",
            {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "error": {"type": "string"},
                    "code": {"type": "string"},
                    "errors": {
                        "type": "object",
                        "additionalProperties": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "required": ["success", "error", "code"],
            },
        )
        self.openapi_generator.add_schema(
            "ResponseValidationError",
            {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "error": {"type": "string"},
                    "detail": {"type": "string"},
                    "code": {"type": "string"},
                },
                "required": ["success", "error", "code"],
            },
        )

    def register_instance(self, cls: Type, instance: Any) -> None:
        """Register a pre-built instance for a class in the DI singleton cache."""
        self._instances_cache[cls] = instance

    def get_instance(self, cls: Type) -> Optional[Any]:
        """Retrieve a cached singleton instance, or None if not registered."""
        return self._instances_cache.get(cls)

    def on_event(self, event_type: str):
        """Decorator to register 'startup' or 'shutdown' handlers."""
        return self._lifecycle_manager.on_event_decorator(event_type)

    def exception_handler(self, exc_class: Type[Exception]):
        """Decorator to register a custom exception handler for exc_class."""

        def decorator(func: Callable):
            if not asyncio.iscoroutinefunction(func):
                logger.warning(
                    "Exception handler %r for %s is synchronous and will block the event loop. "
                    "Consider making it async.",
                    func.__name__,
                    exc_class.__name__,
                )
            self._exception_handlers[exc_class] = func
            return func

        return decorator

    def websocket(self, path: str):
        """Decorator to register a WebSocket endpoint."""
        return self._websocket_manager.websocket_decorator(path)

    # ── Trie dispatch ────────────────────────────────────────────────────────

    def _make_http_dispatch(self, original_router_app: Callable) -> Callable:
        """Return an ASGI callable: HTTP → trie, everything else → Starlette."""
        trie = self._trie
        _dispatch = self._trie_dispatch

        async def dispatch(scope, receive, send):
            if scope["type"] == "http":
                await _dispatch(scope, receive, send)
            else:
                # WebSocket routing and lifespan stay in Starlette's Router
                await original_router_app(scope, receive, send)

        return dispatch

    async def _trie_dispatch(self, scope, receive, send) -> None:
        """Core HTTP dispatch via radix trie — O(k) lookup."""
        status, handler, path_params, allow_header = self._trie.match(
            scope["path"], scope["method"]
        )

        if status == _NOT_FOUND:
            # Use pre-built ASGI dicts — no Response object allocation
            await send(_404_START)
            await send(_404_BODY_MSG)
            return

        if status == _METHOD_NOT_ALLOWED:
            # allow_header is a pre-sorted string stored in the trie node at registration
            headers_405 = [
                (b"content-length", _CL_405),
                (b"content-type", _405_PLAIN_CT),
                (b"allow", allow_header.encode()),
            ]
            await send({"type": "http.response.start", "status": 405, "headers": headers_405})
            await send({"type": "http.response.body",  "body": _405_BODY})
            return

        # _FOUND — two code paths based on handler type
        scope["path_params"] = path_params

        if isinstance(handler, _ASGIHandler):
            # Phase 5b fast-path: no-param endpoints skip Request() creation
            await handler.fn(scope, receive, send)
        else:
            request = Request(scope, receive, send)
            response = await handler(request)
            await response(scope, receive, send)

    # ── Route registration ───────────────────────────────────────────────────

    def _create_decorator(self, path: str, *, http_method: str, **kwargs):
        def decorator(endpoint_func: Callable):
            self._add_route(path, endpoint_func, http_method, **kwargs)
            return endpoint_func

        return decorator

    def _add_route(self, path: str, endpoint_func: Callable, method: str, **kwargs):
        response_model = kwargs.get("response_model")
        compiled = compile_endpoint(endpoint_func, path)

        # Capture flags once — avoids attribute lookup per request
        _has_params        = compiled.has_params
        _has_callable_deps = compiled.has_callable_deps

        async def handler(request):
            try:
                # 2a: skip dict allocation when no callable deps exist
                dependency_cache = {} if _has_callable_deps else None

                if _has_params:
                    # Normal path — extract and validate all parameters
                    kwargs_to_inject, error_response, _background_tasks = (
                        await self._parameter_processor.process_parameters(
                            compiled, request, dependency_cache
                        )
                    )
                    if error_response is not None:
                        return error_response
                else:
                    # 2c: fast-path — no params means no extraction needed
                    kwargs_to_inject = []
                    _background_tasks = None

                payload = await ResponseProcessor.call_endpoint(compiled, kwargs_to_inject)

                return await ResponseProcessor.process_response(
                    payload, response_model, _background_tasks
                )

            except HTTPException as exc:
                exc_handler = self._exception_handlers.get(HTTPException)
                if exc_handler is not None:
                    if asyncio.iscoroutinefunction(exc_handler):
                        return await exc_handler(request, exc)
                    else:
                        return exc_handler(request, exc)
                response = JSONResponse(
                    {"detail": exc.detail}, status_code=exc.status_code
                )
                if exc.headers:
                    for key, value in exc.headers.items():
                        response.headers[key] = value
                return response

            except Exception as exc:
                for exc_class, exc_handler in self._exception_handlers.items():
                    if isinstance(exc, exc_class):
                        if asyncio.iscoroutinefunction(exc_handler):
                            return await exc_handler(request, exc)
                        else:
                            return exc_handler(request, exc)
                return internal_server_error_response()

        # Phase 5b: wrap no-param, no-dep endpoints as ASGI handlers (skip Request creation)
        if not _has_params and not _has_callable_deps:
            _response_model_local = response_model
            _compiled_local = compiled

            async def _fast_asgi(scope, receive, send):
                try:
                    payload = await ResponseProcessor.call_endpoint(_compiled_local, [])
                    resp = await ResponseProcessor.process_response(
                        payload, _response_model_local, None
                    )
                    await resp(scope, receive, send)
                except HTTPException as exc:
                    exc_handler = self._exception_handlers.get(HTTPException)
                    if exc_handler is not None:
                        request = Request(scope, receive, send)
                        if asyncio.iscoroutinefunction(exc_handler):
                            resp = await exc_handler(request, exc)
                        else:
                            resp = exc_handler(request, exc)
                        await resp(scope, receive, send)
                        return
                    err_resp = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
                    if exc.headers:
                        for key, value in exc.headers.items():
                            err_resp.headers[key] = value
                    await err_resp(scope, receive, send)
                except Exception as exc:
                    for exc_cls, exc_handler in self._exception_handlers.items():
                        if isinstance(exc, exc_cls):
                            request = Request(scope, receive, send)
                            if asyncio.iscoroutinefunction(exc_handler):
                                resp = await exc_handler(request, exc)
                            else:
                                resp = exc_handler(request, exc)
                            await resp(scope, receive, send)
                            return
                    await internal_server_error_response()(scope, receive, send)

            self._trie.add(path, method, _ASGIHandler(_fast_asgi))
        else:
            self._trie.add(path, method, handler)

        self.routes.append(
            {"path": path, "method": method, "func": endpoint_func, **kwargs}
        )

        include_in_schema = kwargs.get("include_in_schema", True)
        if include_in_schema:
            self.openapi_generator.generate_route(path, method, endpoint_func, **kwargs)

    def _setup_docs(self):
        if self._docs_setup:
            return

        self._docs_setup = True

        @self.get(self.openapi_config.openapi_url, include_in_schema=False)
        def get_openapi_schema():
            return self.openapi_generator.get_openapi_schema()

        @self.get(self.openapi_config.docs_url, include_in_schema=False)
        def get_scalar_docs():
            html = self.openapi_generator.get_scalar_html(
                self.openapi_config.openapi_url, self.openapi_config.info.title
            )
            return HTMLResponse(html)

        @self.get("/swagger", include_in_schema=False)
        def get_swagger_ui():
            html = self.openapi_generator.get_swagger_ui_html(
                self.openapi_config.openapi_url, self.openapi_config.info.title
            )
            return HTMLResponse(html)

        @self.get(self.openapi_config.redoc_url, include_in_schema=False)
        def get_redoc():
            html = self.openapi_generator.get_redoc_html(
                self.openapi_config.openapi_url, self.openapi_config.info.title
            )
            return HTMLResponse(html)

    async def __call__(self, scope, receive, send):
        """ASGI entry point.

        HTTP: skips Starlette's ServerErrorMiddleware + ExceptionMiddleware and
              goes directly through user middlewares → radix trie (Phase 4).
        Non-HTTP (WebSocket, lifespan): delegated to Starlette's full stack.
        """
        scope["app"] = self  # required by Starlette middleware protocol

        if scope["type"] == "http":
            if not self._docs_setup:
                self._setup_docs()
            if self._http_app is None:
                self._http_app = self._build_http_app()
            await self._http_app(scope, receive, send)
        else:
            # WebSocket routing and lifespan need Starlette's full stack
            if not self._docs_setup:
                self._setup_docs()
            await self._router(scope, receive, send)

    def include_router(self, router, **kwargs):
        """Include a Router's routes into the application."""
        from .router import Router

        if not isinstance(router, Router):
            raise TypeError("Expected Router instance")

        for route_info in router.routes:
            full_path = router.get_full_path(route_info["path"])

            if route_info.get("is_websocket"):
                self._websocket_manager.add_websocket_route(full_path, route_info["func"])
                continue

            route_kwargs = route_info.copy()
            route_kwargs.pop("path", None)
            route_kwargs.pop("method", None)
            route_kwargs.pop("func", None)
            route_kwargs.pop("is_websocket", None)

            self._add_route(
                full_path, route_info["func"], route_info["method"], **route_kwargs
            )

    def _build_http_app(self) -> Callable:
        """Build HTTP ASGI app: only user middlewares wrap our trie dispatch.

        Starlette's ServerErrorMiddleware and ExceptionMiddleware are skipped for
        HTTP requests — their job is already done by the try/except in each handler
        closure. This eliminates ~1.5µs per request from two extra coroutine calls.
        """
        app: Callable = self._trie_dispatch  # bound method → ASGI-compatible
        for mw in reversed(self.middleware_stack):
            app = mw["func"](app=app, **mw["options"])
        return app

    def add_middleware(self, middleware_class, **options):
        """Add a middleware to the application stack."""
        apply_middleware_to_router(self._router, middleware_class, **options)
        self.middleware_stack.append({"func": middleware_class, "options": options})
        self._http_app = None  # invalidate: rebuild on next HTTP request

    def middleware(self, middleware_type="http"):
        """Decorator to register a function as ASGI middleware."""

        def decorator(middleware_func):
            DecoratedMiddleware = create_decorated_middleware_class(
                middleware_func, middleware_type
            )
            self.add_middleware(DecoratedMiddleware)
            return middleware_func

        return decorator
