"""Tachyon application facade — composes collaborators, exposes the public API."""

import logging
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Type

from starlette.applications import Starlette

from ..core.lifecycle import LifecycleManager
from ..core.websocket import WebSocketManager
from ..middlewares.core import (
    apply_middleware_to_router,
    create_decorated_middleware_class,
)
from ..openapi import OpenAPIConfig, OpenAPIGenerator, create_openapi_config
from ..processing.dependencies import DependencyResolver
from ..processing.dispatch import TachyonDispatcher
from ..processing.parameters import ParameterProcessor
from ..routing.trie import RadixTrie

from ._404 import _404_BODY_MSG, _404_START
from ._405 import _405_BODY, _405_PLAIN_CT, _CL_405
from ._asgi_entry import ASGIEntry
from ._asgi_handler import _ASGIHandler
from ._docs_routes import DocsRoutes
from ._docs_schemas import CommonSchemas
from ._exception_table import ExceptionTable
from ._fast_asgi_factory import FastASGIFactory
from ._handler_factory import HandlerFactory
from ._http_dispatch import HTTPDispatcher
from ._mw_stack import MiddlewareStack
from ._registry import RouteRegistry
from ._route_installer import RouteInstaller

try:
    from ..cache import set_cache_config
except ImportError:  # pragma: no cover
    set_cache_config = None  # type: ignore

logger = logging.getLogger(__name__)


class Tachyon:
    """Tachyon application — composes the framework's collaborators."""

    def __init__(
        self,
        openapi_config: Optional[OpenAPIConfig] = None,
        cache_config: Optional[Any] = None,
        lifespan: Optional[Callable] = None,
        max_body_size: int = 2 * 1024 * 1024,
    ):
        self.max_body_size = max_body_size
        self._lifecycle_manager = LifecycleManager(lifespan)

        # Starlette stays for WebSocket routing and lifespan
        self._router = Starlette(
            lifespan=self._lifecycle_manager.create_combined_lifespan()
        )

        # Radix trie replaces Starlette's O(N) regex route scan
        self._trie = RadixTrie()

        # Cython dispatcher reads C-level struct fields per request
        self._dispatcher = TachyonDispatcher(
            trie=self._trie,
            _404_start=_404_START,
            _404_body=_404_BODY_MSG,
            _405_body=_405_BODY,
            _405_ct=_405_PLAIN_CT,
            _405_cl=_CL_405,
            asgi_handler_class=_ASGIHandler,
        )

        # Route HTTP to trie, non-HTTP to Starlette
        _original_router_app = self._router.router.app
        self._router.router.middleware_stack = HTTPDispatcher(
            dispatcher=self._dispatcher,
            fallback=_original_router_app,
        )

        # Collaborators
        self._websocket_manager = WebSocketManager(self._router)
        self._parameter_processor = ParameterProcessor(self)
        self._dependency_resolver = DependencyResolver(self)

        self._registry = RouteRegistry()
        self._exc_table = ExceptionTable()
        self._mw_stack = MiddlewareStack()
        self._handler_factory = HandlerFactory(self)
        self._fast_asgi_factory = FastASGIFactory(self)
        self._installer = RouteInstaller(self)
        self._docs_routes = DocsRoutes(self)
        self._asgi_entry = ASGIEntry(self)

        # DI / state
        self._instances_cache: Dict[Type, Any] = {}
        self.state = self._router.state
        self.dependency_overrides: Dict[Any, Any] = {}

        # OpenAPI
        self.openapi_config = openapi_config or create_openapi_config()
        self.openapi_generator = OpenAPIGenerator(self.openapi_config)
        CommonSchemas.register(self.openapi_generator)

        # Cache configuration (optional)
        self.cache_config = cache_config
        if cache_config is not None and set_cache_config is not None:
            try:
                set_cache_config(cache_config)
            except Exception as exc:
                logger.warning("Failed to apply cache config: %s", exc)

        # Lazily-built HTTP ASGI app (user middlewares → trie dispatcher)
        self._http_app: Optional[Callable] = None

        # Bind get/post/put/... decorators
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
            setattr(
                self,
                method.lower(),
                partial(self._create_decorator, http_method=method),
            )

    # ── Public introspection ────────────────────────────────────────────────

    @property
    def routes(self) -> List[Dict[str, Any]]:
        return self._registry.routes

    @property
    def middleware_stack(self) -> List[Dict[str, Any]]:
        return self._mw_stack.middlewares

    def register_instance(self, cls: Type, instance: Any) -> None:
        """Register a pre-built instance for a class in the DI singleton cache."""
        self._instances_cache[cls] = instance

    def get_instance(self, cls: Type) -> Optional[Any]:
        return self._instances_cache.get(cls)

    # ── Decorators ──────────────────────────────────────────────────────────

    def on_event(self, event_type: str):
        return self._lifecycle_manager.on_event_decorator(event_type)

    def exception_handler(self, exc_class: Type[Exception]):
        def decorator(func: Callable) -> Callable:
            self._exc_table.register(exc_class, func)
            return func
        return decorator

    def websocket(self, path: str):
        return self._websocket_manager.websocket_decorator(path)

    def middleware(self, middleware_type: str = "http"):
        def decorator(middleware_func: Callable) -> Callable:
            cls = create_decorated_middleware_class(middleware_func, middleware_type)
            self.add_middleware(cls)
            return middleware_func
        return decorator

    # ── Route registration ──────────────────────────────────────────────────

    def _create_decorator(self, path: str, *, http_method: str, **kwargs: Any):
        def decorator(endpoint_func: Callable) -> Callable:
            self._installer.install(path, http_method, endpoint_func, **kwargs)
            return endpoint_func
        return decorator

    def include_router(self, router, **kwargs: Any) -> None:
        from ..router import Router

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

            self._installer.install(
                full_path, route_info["method"], route_info["func"], **route_kwargs
            )

    # ── Middleware ──────────────────────────────────────────────────────────

    def add_middleware(self, middleware_class, **options: Any) -> None:
        apply_middleware_to_router(self._router, middleware_class, **options)
        self._mw_stack.add(middleware_class, **options)
        self._http_app = None  # invalidate — rebuild on next HTTP request

    # ── ASGI entry ──────────────────────────────────────────────────────────

    async def __call__(self, scope, receive, send) -> None:
        await self._asgi_entry(scope, receive, send)


__all__ = ["Tachyon"]
