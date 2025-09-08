"""
Tachyon Web Framework - Main Application Module

This module contains the core Tachyon class that provides a lightweight,
FastAPI-inspired web framework with built-in dependency injection,
parameter validation, and automatic type conversion.
"""

import inspect
from functools import partial
from typing import Any, Type, Callable

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..dependencies.injection import Depends, _registry
from ..openapi.schema import (
    OpenAPIGenerator,
    OpenAPIConfig,
    create_openapi_config,
)
from ..middlewares import create_decorated_middleware_class

from ..dependencies.resolver import DependencyResolver
from ..processing.parameters import ParameterProcessor, _NotProcessed
from ..processing.responses import ResponseProcessor
from ..openapi.builder import OpenAPIBuilder
from ..routing.routes import TachyonRouter

try:
    from ..features.cache import set_cache_config
except ImportError:
    set_cache_config = None  # type: ignore


class Tachyon:
    """
    Main Tachyon application class.

    Provides a web framework with automatic parameter validation, dependency injection,
    and type conversion. Built on top of Starlette for ASGI compatibility.

    Attributes:
        _router: Internal Starlette application instance
        routes: List of registered routes for introspection
        _instances_cache: Cache for dependency injection singleton instances
        openapi_config: Configuration for OpenAPI documentation
        openapi_generator: Generator for OpenAPI schema and documentation
    """

    def __init__(self, openapi_config: OpenAPIConfig = None, cache_config=None):
        """
        Initialize a new Tachyon application instance.

        Args:
            openapi_config: Optional OpenAPI configuration. If not provided,
                          uses default configuration similar to FastAPI.
            cache_config: Optional cache configuration (tachyon_api.cache.CacheConfig).
                          If provided, it will be set as the active cache configuration.
        """
        # Create dependency resolver and router
        self._dependency_resolver = DependencyResolver()
        self._tachyon_router = TachyonRouter(self._dependency_resolver)

        # Create Starlette app with our routes
        self._router = Starlette(routes=self._tachyon_router.get_starlette_routes())
        self.routes = []

        # Initialize OpenAPI configuration and generator
        self.openapi_config = openapi_config or create_openapi_config()
        self.openapi_generator = OpenAPIGenerator(self.openapi_config)
        self._openapi_builder = OpenAPIBuilder(
            self.openapi_config, self.openapi_generator
        )
        self._docs_setup = False

        # Apply cache configuration if provided
        self.cache_config = cache_config
        if cache_config is not None and set_cache_config is not None:
            try:
                set_cache_config(cache_config)
            except Exception:
                # Do not break app initialization if cache setup fails
                pass

        # Dynamically create HTTP method decorators (get, post, put, delete, etc.)
        http_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]

        for method in http_methods:
            setattr(
                self,
                method.lower(),
                partial(self._create_decorator, http_method=method),
            )

    def _resolve_dependency(self, cls: Type) -> Any:
        """
        Resolve a dependency using the dependency resolver.

        This is a convenience method that delegates to the DependencyResolver instance.

        Args:
            cls: The class type to resolve and instantiate

        Returns:
            An instance of the requested class with all dependencies resolved
        """
        return self._dependency_resolver.resolve_dependency(cls)

    def _add_route(self, path: str, endpoint_func: Callable, method: str, **kwargs):
        """
        Register a route with the application.

        This method now uses the Starlette-native TachyonRouter for better
        compatibility with future Starlette/Rust versions.

        Args:
            path: URL path pattern (e.g., "/users/{user_id}")
            endpoint_func: The endpoint function to handle requests
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            **kwargs: Additional route metadata
        """
        # Add route to our Tachyon router
        route = self._tachyon_router.add_route(
            path=path, endpoint=endpoint_func, methods=[method], **kwargs
        )

        # Store route info for backward compatibility and OpenAPI generation
        self.routes.append(route.get_endpoint_info())

        # Generate OpenAPI documentation for this route
        include_in_schema = kwargs.get("include_in_schema", True)
        if include_in_schema:
            self._openapi_builder.generate_openapi_for_route(
                path, method, endpoint_func, **kwargs
            )

    def _create_decorator(self, path: str, *, http_method: str, **kwargs):
        """
        Create a decorator for the specified HTTP method.

        This factory method creates method-specific decorators (e.g., @app.get, @app.post)
        that register endpoint functions with the application.

        Args:
            path: URL path pattern (supports path parameters with {param} syntax)
            http_method: HTTP method name (GET, POST, PUT, DELETE, etc.)

        Returns:
            A decorator function that registers the endpoint
        """

        def decorator(endpoint_func: Callable):
            self._add_route(path, endpoint_func, http_method, **kwargs)
            return endpoint_func

        return decorator

    def _add_route(self, path: str, endpoint_func: Callable, method: str, **kwargs):
        """
        Register a route with the application and create an async handler.

        This is the core method that handles parameter injection, validation, and
        type conversion. It creates an async handler that processes requests and
        automatically injects dependencies, path parameters, query parameters, and
        request body data into the endpoint function.

        Args:
            path: URL path pattern (e.g., "/users/{user_id}")
            endpoint_func: The endpoint function to handle requests
            method: HTTP method (GET, POST, PUT, DELETE, etc.)

        Note:
            The created handler processes parameters in the following order:
            1. Dependencies (explicit with Depends() or implicit via @injectable)
            2. Body parameters (JSON request body validated against Struct models)
            3. Query parameters (URL query string with type conversion)
            4. Path parameters (both explicit with Path() and implicit from URL)
        """

        response_model = kwargs.get("response_model")

        async def handler(request):
            """
            Async request handler that processes parameters and calls the endpoint.

            This handler analyzes the endpoint function signature and automatically
            injects the appropriate values based on parameter annotations and defaults.
            """
            kwargs_to_inject = {}
            sig = inspect.signature(endpoint_func)
            query_params = request.query_params
            path_params = request.path_params
            _raw_body = None

            # Process each parameter in the endpoint function signature
            for param in sig.parameters.values():
                # Determine if this parameter is a dependency
                is_explicit_dependency = isinstance(param.default, Depends)
                is_implicit_dependency = (
                    param.default is inspect.Parameter.empty
                    and param.annotation in _registry
                )

                # Process dependencies (explicit and implicit)
                if is_explicit_dependency or is_implicit_dependency:
                    target_class = param.annotation
                    kwargs_to_inject[param.name] = self._resolve_dependency(
                        target_class
                    )
                    continue

                # Process other parameter types using ParameterProcessor
                result = await ParameterProcessor.process_parameter(
                    param,
                    request,
                    path_params,
                    query_params,
                    _raw_body,
                    is_explicit_dependency,
                    is_implicit_dependency,
                )

                # If parameter was processed and returned a value/error, handle it
                if not isinstance(result, _NotProcessed):
                    if isinstance(result, JSONResponse):
                        return result  # Error response
                    kwargs_to_inject[param.name] = result

            # Process the response using ResponseProcessor
            return await ResponseProcessor.process_response(
                endpoint_func, kwargs_to_inject, response_model
            )

        # Register the route with Starlette
        route = Route(path, endpoint=handler, methods=[method])
        self._router.routes.append(route)
        self.routes.append(
            {"path": path, "method": method, "func": endpoint_func, **kwargs}
        )

        # Generate OpenAPI documentation for this route
        include_in_schema = kwargs.get("include_in_schema", True)
        if include_in_schema:
            self._openapi_builder.generate_openapi_for_route(
                path, method, endpoint_func, **kwargs
            )

    def _setup_docs(self):
        """
        Setup OpenAPI documentation endpoints.

        This method registers the routes for serving OpenAPI JSON schema,
        Swagger UI, and ReDoc documentation interfaces.
        """
        if self._docs_setup:
            return

        self._docs_setup = True
        self._openapi_builder.setup_docs(self)

    async def __call__(self, scope, receive, send):
        """
        ASGI application entry point.

        Delegates request handling to the internal Starlette application.
        This makes Tachyon compatible with ASGI servers like Uvicorn.
        """
        # Setup documentation endpoints on first request
        if not self._docs_setup:
            self._setup_docs()
        await self._router(scope, receive, send)

    def include_router(self, router, **kwargs):
        """
        Include a Router instance in the application.

        This method registers all routes from the router with the main application,
        applying the router's prefix, tags, and dependencies.

        Args:
            router: The Router instance to include
            **kwargs: Additional options (currently reserved for future use)
        """
        from ..routing.router import Router

        if not isinstance(router, Router):
            raise TypeError("Expected Router instance")

        # Register all routes from the router
        for route_info in router.routes:
            # Get the full path with prefix
            full_path = router.get_full_path(route_info["path"])

            # Create a copy of route info with the full path
            route_kwargs = route_info.copy()
            route_kwargs.pop("path", None)
            route_kwargs.pop("method", None)
            route_kwargs.pop("func", None)

            # Register the route with the main app
            self._add_route(
                full_path, route_info["func"], route_info["method"], **route_kwargs
            )

    def add_middleware(self, middleware_class, **options):
        """
        Add a middleware to the Starlette application.

        This method directly uses Starlette's native middleware API for maximum
        compatibility with future Starlette/Rust versions.

        Args:
            middleware_class: The middleware class.
            **options: Options to be passed to the middleware constructor.
        """
        # Use Starlette's native middleware API directly
        self._router.add_middleware(middleware_class, **options)

    def middleware(self, middleware_type="http"):
        """
        Decorator for adding a middleware to the application.
        Similar to route decorators (@app.get, etc.)

        Args:
            middleware_type: Type of middleware ('http' by default)

        Returns:
            A decorator that registers the decorated function as middleware.
        """

        def decorator(middleware_func):
            # Create a middleware class from the decorated function
            DecoratedMiddleware = create_decorated_middleware_class(
                middleware_func, middleware_type
            )
            # Register the middleware using Starlette's native API
            self.add_middleware(DecoratedMiddleware)
            return middleware_func

        return decorator

    @property
    def middleware_stack(self):
        """
        Get the current middleware stack for introspection.

        This property provides access to Starlette's middleware stack for
        debugging and testing purposes.

        Returns:
            List of middleware classes configured on the Starlette app
        """
        return getattr(self._router, "user_middleware", [])
