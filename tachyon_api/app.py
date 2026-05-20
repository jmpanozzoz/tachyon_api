"""Core Tachyon application class."""

import asyncio
import inspect
import logging
from functools import partial
from typing import Any, Dict, List, Type, Callable, Optional

logger = logging.getLogger(__name__)

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .di import Depends, _registry
from .models import Struct
from .openapi import (
    OpenAPIGenerator,
    OpenAPIConfig,
    create_openapi_config,
    build_components_for_struct,
)
from .params import Body, Query, Path, Header, Cookie
from .exceptions import HTTPException
from .middlewares.core import (
    apply_middleware_to_router,
    create_decorated_middleware_class,
)
from .responses import (
    HTMLResponse,
    internal_server_error_response,
)
from .utils import TypeUtils
from .core.lifecycle import LifecycleManager
from .core.websocket import WebSocketManager
from .processing.parameters import ParameterProcessor
from .processing.dependencies import DependencyResolver
from .processing.response_processor import ResponseProcessor

try:
    from .cache import set_cache_config
except ImportError:
    set_cache_config = None  # type: ignore


class Tachyon:
    def __init__(
        self,
        openapi_config: Optional[OpenAPIConfig] = None,
        cache_config: Optional[Any] = None,
        lifespan: Optional[Callable] = None,
    ):
        self._lifecycle_manager = LifecycleManager(lifespan)
        self._exception_handlers: Dict[Type[Exception], Callable] = {}
        self._router = Starlette(lifespan=self._lifecycle_manager.create_combined_lifespan())
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

    def on_event(self, event_type: str):
        """Decorator to register 'startup' or 'shutdown' handlers."""
        return self._lifecycle_manager.on_event_decorator(event_type)

    def exception_handler(self, exc_class: Type[Exception]):
        """Decorator to register a custom exception handler for exc_class."""

        def decorator(func: Callable):
            self._exception_handlers[exc_class] = func
            return func

        return decorator

    def websocket(self, path: str):
        """Decorator to register a WebSocket endpoint."""
        return self._websocket_manager.websocket_decorator(path)

    def _create_decorator(self, path: str, *, http_method: str, **kwargs):
        def decorator(endpoint_func: Callable):
            self._add_route(path, endpoint_func, http_method, **kwargs)
            return endpoint_func

        return decorator

    def _add_route(self, path: str, endpoint_func: Callable, method: str, **kwargs):
        response_model = kwargs.get("response_model")

        async def handler(request):
            try:
                dependency_cache = {}
                kwargs_to_inject, error_response, _background_tasks = await self._parameter_processor.process_parameters(
                    endpoint_func, request, dependency_cache
                )

                if error_response is not None:
                    return error_response

                payload = await ResponseProcessor.call_endpoint(
                    endpoint_func, kwargs_to_inject
                )

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
                for exc_class, handler in self._exception_handlers.items():
                    if isinstance(exc, exc_class):
                        if asyncio.iscoroutinefunction(handler):
                            return await handler(request, exc)
                        else:
                            return handler(request, exc)
                return internal_server_error_response()

        route = Route(path, endpoint=handler, methods=[method])
        self._router.routes.append(route)
        self.routes.append(
            {"path": path, "method": method, "func": endpoint_func, **kwargs}
        )

        include_in_schema = kwargs.get("include_in_schema", True)
        if include_in_schema:
            self._generate_openapi_for_route(path, method, endpoint_func, **kwargs)

    _PARAM_IN = {Query: "query", Header: "header", Cookie: "cookie"}

    def _generate_openapi_for_route(
        self, path: str, method: str, endpoint_func: Callable, **kwargs
    ):
        sig = inspect.signature(endpoint_func)
        operation = {
            "summary": kwargs.get("summary", self._generate_summary_from_function(endpoint_func)),
            "description": kwargs.get("description", endpoint_func.__doc__ or ""),
            "responses": {
                "200": {
                    "description": "Successful Response",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "422": {
                    "description": "Validation Error",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}}},
                },
                "500": {
                    "description": "Response Validation Error",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ResponseValidationError"}}},
                },
            },
        }

        response_model = kwargs.get("response_model")
        try:
            is_struct_model = response_model is not None and isinstance(response_model, type) and issubclass(response_model, Struct)
        except TypeError:
            is_struct_model = False
        if is_struct_model:
            for name, schema in build_components_for_struct(response_model).items():
                self.openapi_generator.add_schema(name, schema)
            operation["responses"]["200"]["content"]["application/json"]["schema"] = {
                "$ref": f"#/components/schemas/{response_model.__name__}"
            }

        if "tags" in kwargs:
            operation["tags"] = kwargs["tags"]

        parameters = []
        request_body_schema = None

        for param in sig.parameters.values():
            if isinstance(param.default, Depends) or (
                param.default is inspect.Parameter.empty and param.annotation in _registry
            ):
                continue

            for param_cls, location in self._PARAM_IN.items():
                if isinstance(param.default, param_cls):
                    parameters.append({
                        "name": param.name,
                        "in": location,
                        "required": param.default.default is ...,
                        "schema": self._build_param_openapi_schema(param.annotation),
                        "description": getattr(param.default, "description", ""),
                    })
                    break
            else:
                if isinstance(param.default, Path) or self._is_path_parameter(param.name, path):
                    parameters.append({
                        "name": param.name,
                        "in": "path",
                        "required": True,
                        "schema": self._build_param_openapi_schema(param.annotation),
                        "description": getattr(param.default, "description", "") if isinstance(param.default, Path) else "",
                    })
                elif isinstance(param.default, Body) and isinstance(param.annotation, type) and issubclass(param.annotation, Struct):
                    for name, schema in build_components_for_struct(param.annotation).items():
                        self.openapi_generator.add_schema(name, schema)
                    request_body_schema = {
                        "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{param.annotation.__name__}"}}},
                        "required": True,
                    }

        if parameters:
            operation["parameters"] = parameters
        if request_body_schema:
            operation["requestBody"] = request_body_schema

        self.openapi_generator.add_path(path, method, operation)

    @staticmethod
    def _generate_summary_from_function(func: Callable) -> str:
        return func.__name__.replace("_", " ").title()

    @staticmethod
    def _is_path_parameter(param_name: str, path: str) -> bool:
        return f"{{{param_name}}}" in path

    @staticmethod
    def _build_param_openapi_schema(python_type: Type) -> Dict[str, Any]:
        inner_type, nullable = TypeUtils.unwrap_optional(python_type)
        is_list, item_type = TypeUtils.is_list_type(inner_type)
        if is_list:
            base_item_type, item_nullable = TypeUtils.unwrap_optional(item_type)
            schema = {
                "type": "array",
                "items": {"type": TypeUtils.get_openapi_type(base_item_type)},
            }
            if item_nullable:
                schema["items"]["nullable"] = True
        else:
            schema = {"type": TypeUtils.get_openapi_type(inner_type)}

        if nullable:
            schema["nullable"] = True
        return schema

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
        """ASGI entry point."""
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

    def add_middleware(self, middleware_class, **options):
        """Add a middleware to the application stack."""
        apply_middleware_to_router(self._router, middleware_class, **options)
        self.middleware_stack.append({"func": middleware_class, "options": options})

    def middleware(self, middleware_type="http"):
        """Decorator to register a function as ASGI middleware."""

        def decorator(middleware_func):
            DecoratedMiddleware = create_decorated_middleware_class(
                middleware_func, middleware_type
            )
            self.add_middleware(DecoratedMiddleware)
            return middleware_func

        return decorator
