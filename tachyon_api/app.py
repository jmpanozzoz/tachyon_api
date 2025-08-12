"""
Tachyon Web Framework - Main Application Module

This module contains the core Tachyon class that provides a lightweight,
FastAPI-inspired web framework with built-in dependency injection,
parameter validation, and automatic type conversion.
"""

import asyncio
import inspect
import msgspec
from functools import partial
from typing import Any, Dict, Type, Union, Callable

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from .di import Depends, _registry
from .models import Struct
from .openapi import (
    OpenAPIGenerator,
    OpenAPIConfig,
    create_openapi_config,
    _generate_schema_for_struct,
)
from .params import Body, Query, Path
from .middlewares.core import (
    apply_middleware_to_router,
    create_decorated_middleware_class,
)


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

    def __init__(self, openapi_config: OpenAPIConfig = None):
        """
        Initialize a new Tachyon application instance.

        Args:
            openapi_config: Optional OpenAPI configuration. If not provided,
                          uses default configuration similar to FastAPI.
        """
        self._router = Starlette()
        self.routes = []
        self.middleware_stack = []
        self._instances_cache: Dict[Type, Any] = {}

        # Initialize OpenAPI configuration and generator
        self.openapi_config = openapi_config or create_openapi_config()
        self.openapi_generator = OpenAPIGenerator(self.openapi_config)
        self._docs_setup = False

        # Dynamically create HTTP method decorators (get, post, put, delete, etc.)
        http_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]

        for method in http_methods:
            setattr(
                self,
                method.lower(),
                partial(self._create_decorator, http_method=method),
            )

    @staticmethod
    def _convert_value(
        value_str: str,
        target_type: Type,
        param_name: str,
        is_path_param: bool = False,  # noqa
    ) -> Union[Any, JSONResponse]:
        """
        Convert a string value to the target type with appropriate error handling.

        This method handles type conversion for query and path parameters,
        including special handling for boolean values and proper error responses.

        Args:
            value_str: The string value to convert
            target_type: The target Python type to convert to
            param_name: Name of the parameter (for error messages)
            is_path_param: Whether this is a path parameter (affects error response)

        Returns:
            The converted value, or a JSONResponse with appropriate error code

        Note:
            - Boolean conversion accepts: "true", "1", "t", "yes" (case-insensitive)
            - Path parameter errors return 404, query parameter errors return 422
        """
        try:
            if target_type is bool:
                return value_str.lower() in ("true", "1", "t", "yes")
            elif target_type is not str:
                return target_type(value_str)
            else:
                return value_str
        except (ValueError, TypeError):
            if is_path_param:
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            else:
                type_name = "integer" if target_type is int else target_type.__name__
                return JSONResponse(
                    {"detail": f"Invalid value for {type_name} conversion"},
                    status_code=422,
                )

    def _resolve_dependency(self, cls: Type) -> Any:
        """
        Resolve a dependency and its sub-dependencies recursively.

        This method implements dependency injection with singleton pattern,
        automatically resolving constructor dependencies and caching instances.

        Args:
            cls: The class type to resolve and instantiate

        Returns:
            An instance of the requested class with all dependencies resolved

        Raises:
            TypeError: If the class cannot be instantiated or is not marked as injectable

        Note:
            - Uses singleton pattern - instances are cached and reused
            - Supports both @injectable decorated classes and simple classes
            - Recursively resolves constructor dependencies
        """
        # Return cached instance if available (singleton pattern)
        if cls in self._instances_cache:
            return self._instances_cache[cls]

        # For non-injectable classes, try to create without arguments
        if cls not in _registry:
            try:
                # Works for classes without __init__ or with no-arg __init__
                return cls()
            except TypeError:
                raise TypeError(
                    f"Cannot resolve dependency '{cls.__name__}'. "
                    f"Did you forget to mark it with @injectable?"
                )

        # For injectable classes, resolve constructor dependencies
        sig = inspect.signature(cls)
        dependencies = {}

        # Recursively resolve each constructor parameter
        for param in sig.parameters.values():
            if param.name != "self":
                dependencies[param.name] = self._resolve_dependency(param.annotation)

        # Create instance with resolved dependencies and cache it
        instance = cls(**dependencies)
        self._instances_cache[cls] = instance
        return instance

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

                # Process Body parameters (JSON request body)
                elif isinstance(param.default, Body):
                    model_class = param.annotation
                    if not issubclass(model_class, Struct):
                        raise TypeError(
                            "Body type must be an instance of Tachyon_api.models.Struct"
                        )

                    decoder = msgspec.json.Decoder(model_class)
                    try:
                        if _raw_body is None:
                            _raw_body = await request.body()
                        validated_data = decoder.decode(_raw_body)
                        kwargs_to_inject[param.name] = validated_data
                    except msgspec.ValidationError as e:
                        return JSONResponse({"detail": str(e)}, status_code=422)

                # Process Query parameters (URL query string)
                elif isinstance(param.default, Query):
                    query_info = param.default
                    param_name = param.name

                    if param_name in query_params:
                        value_str = query_params[param_name]
                        converted_value = self._convert_value(
                            value_str, param.annotation, param_name, is_path_param=False
                        )
                        # Return error response if conversion failed
                        if isinstance(converted_value, JSONResponse):
                            return converted_value
                        kwargs_to_inject[param_name] = converted_value

                    elif query_info.default is not ...:
                        # Use default value if parameter is optional
                        kwargs_to_inject[param.name] = query_info.default
                    else:
                        # Return error if required parameter is missing
                        return JSONResponse(
                            {
                                "detail": f"Missing required query parameter: {param_name}"
                            },
                            status_code=422,
                        )

                # Process explicit Path parameters (with Path() annotation)
                elif isinstance(param.default, Path):
                    param_name = param.name
                    if param_name in path_params:
                        value_str = path_params[param_name]
                        converted_value = self._convert_value(
                            value_str, param.annotation, param_name, is_path_param=True
                        )
                        # Return 404 if conversion failed
                        if isinstance(converted_value, JSONResponse):
                            return converted_value
                        kwargs_to_inject[param_name] = converted_value
                    else:
                        return JSONResponse({"detail": "Not Found"}, status_code=404)

                # Process implicit Path parameters (URL path variables without Path())
                elif (
                    param.default is inspect.Parameter.empty
                    and param.name in path_params
                    and not is_explicit_dependency
                    and not is_implicit_dependency
                ):
                    param_name = param.name
                    value_str = path_params[param_name]
                    converted_value = self._convert_value(
                        value_str, param.annotation, param_name, is_path_param=True
                    )
                    # Return 404 if conversion failed
                    if isinstance(converted_value, JSONResponse):
                        return converted_value
                    kwargs_to_inject[param_name] = converted_value

            # Call the endpoint function with injected parameters
            if asyncio.iscoroutinefunction(endpoint_func):
                payload = await endpoint_func(**kwargs_to_inject)
            else:
                payload = endpoint_func(**kwargs_to_inject)

            # If the endpoint already returned a Response object, return it directly
            if isinstance(payload, Response):
                return payload

            # Convert Struct objects to dictionaries for JSON serialization
            if isinstance(payload, Struct):
                payload = msgspec.to_builtins(payload)
            elif isinstance(payload, dict):
                # Convert any Struct values in the dictionary
                for key, value in payload.items():
                    if isinstance(value, Struct):
                        payload[key] = msgspec.to_builtins(value)

            return JSONResponse(payload)

        # Register the route with Starlette
        route = Route(path, endpoint=handler, methods=[method])
        self._router.routes.append(route)
        self.routes.append(
            {"path": path, "method": method, "func": endpoint_func, **kwargs}
        )

        # Generate OpenAPI documentation for this route
        include_in_schema = kwargs.get("include_in_schema", True)
        if include_in_schema:
            self._generate_openapi_for_route(path, method, endpoint_func, **kwargs)

    def _generate_openapi_for_route(
        self, path: str, method: str, endpoint_func: Callable, **kwargs
    ):
        """
        Generate OpenAPI documentation for a specific route.

        This method analyzes the endpoint function signature and generates appropriate
        OpenAPI schema entries for parameters, request body, and responses.

        Args:
            path: URL path pattern
            method: HTTP method
            endpoint_func: The endpoint function
            **kwargs: Additional route metadata (summary, description, tags, etc.)
        """
        sig = inspect.signature(endpoint_func)

        # Build the OpenAPI operation object
        operation = {
            "summary": kwargs.get(
                "summary", self._generate_summary_from_function(endpoint_func)
            ),
            "description": kwargs.get("description", endpoint_func.__doc__ or ""),
            "responses": {
                "200": {
                    "description": "Successful Response",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                }
            },
        }

        # Add tags if provided
        if "tags" in kwargs:
            operation["tags"] = kwargs["tags"]

        # Process parameters from function signature
        parameters = []
        request_body_schema = None

        for param in sig.parameters.values():
            # Skip dependency parameters
            if isinstance(param.default, Depends) or (
                param.default is inspect.Parameter.empty
                and param.annotation in _registry
            ):
                continue

            # Process query parameters
            elif isinstance(param.default, Query):
                parameters.append(
                    {
                        "name": param.name,
                        "in": "query",
                        "required": param.default.default is ...,
                        "schema": {"type": self._get_openapi_type(param.annotation)},
                        "description": getattr(param.default, "description", ""),
                    }
                )

            # Process path parameters
            elif isinstance(param.default, Path) or self._is_path_parameter(
                param.name, path
            ):
                parameters.append(
                    {
                        "name": param.name,
                        "in": "path",
                        "required": True,
                        "schema": {"type": self._get_openapi_type(param.annotation)},
                        "description": getattr(param.default, "description", "")
                        if isinstance(param.default, Path)
                        else "",
                    }
                )

            # Process body parameters
            elif isinstance(param.default, Body):
                model_class = param.annotation
                if issubclass(model_class, Struct):
                    schema_name = model_class.__name__
                    # Add schema to components
                    self.openapi_generator.add_schema(
                        schema_name, _generate_schema_for_struct(model_class)
                    )

                    request_body_schema = {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": f"#/components/schemas/{schema_name}"
                                }
                            }
                        },
                        "required": True,
                    }

        # Add parameters to operation if any exist
        if parameters:
            operation["parameters"] = parameters

        # Add request body if it exists
        if request_body_schema:
            operation["requestBody"] = request_body_schema

        # Add the operation to the OpenAPI schema
        self.openapi_generator.add_path(path, method, operation)

    @staticmethod
    def _generate_summary_from_function(func: Callable) -> str:
        """Generate a human-readable summary from function name."""
        return func.__name__.replace("_", " ").title()

    @staticmethod
    def _is_path_parameter(param_name: str, path: str) -> bool:
        """Check if a parameter name corresponds to a path parameter in the URL."""
        return f"{{{param_name}}}" in path

    @staticmethod
    def _get_openapi_type(python_type: Type) -> str:
        """Convert Python type to OpenAPI schema type."""
        type_map: Dict[Type, str] = {
            int: "integer",
            str: "string",
            bool: "boolean",
            float: "number",
        }
        return type_map.get(python_type, "string")

    def _setup_docs(self):
        """
        Setup OpenAPI documentation endpoints.

        This method registers the routes for serving OpenAPI JSON schema,
        Swagger UI, and ReDoc documentation interfaces.
        """
        if self._docs_setup:
            return

        self._docs_setup = True

        # OpenAPI JSON schema endpoint
        @self.get(self.openapi_config.openapi_url, include_in_schema=False)
        def get_openapi_schema():
            """Serve the OpenAPI JSON schema."""
            return self.openapi_generator.get_openapi_schema()

        # Scalar API Reference documentation endpoint (default for /docs)
        @self.get(self.openapi_config.docs_url, include_in_schema=False)
        def get_scalar_docs():
            """Serve the Scalar API Reference documentation interface."""
            html = self.openapi_generator.get_scalar_html(
                self.openapi_config.openapi_url, self.openapi_config.info.title
            )
            return HTMLResponse(html)

        # Swagger UI documentation endpoint (legacy support)
        @self.get("/swagger", include_in_schema=False)
        def get_swagger_ui():
            """Serve the Swagger UI documentation interface."""
            html = self.openapi_generator.get_swagger_ui_html(
                self.openapi_config.openapi_url, self.openapi_config.info.title
            )
            return HTMLResponse(html)

        # ReDoc documentation endpoint
        @self.get(self.openapi_config.redoc_url, include_in_schema=False)
        def get_redoc():
            """Serve the ReDoc documentation interface."""
            html = self.openapi_generator.get_redoc_html(
                self.openapi_config.openapi_url, self.openapi_config.info.title
            )
            return HTMLResponse(html)

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
        from .router import Router

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
        Adds a middleware to the application's stack.

        Middlewares are processed in the order they are added. They follow
        the ASGI middleware specification.

        Args:
            middleware_class: The middleware class.
            **options: Options to be passed to the middleware constructor.
        """
        # Usar helper centralizado para aplicar el middleware sobre Starlette
        apply_middleware_to_router(self._router, middleware_class, **options)

        if not hasattr(self, "middleware_stack"):
            self.middleware_stack = []
        self.middleware_stack.append({"func": middleware_class, "options": options})

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
            # Crear una clase de middleware a partir de la función decorada
            DecoratedMiddleware = create_decorated_middleware_class(
                middleware_func, middleware_type
            )
            # Registrar el middleware usando el método existente
            self.add_middleware(DecoratedMiddleware)
            return middleware_func

        return decorator
