"""
Tachyon Web Framework - Main Application Module

This module contains the core Tachyon class that provides a lightweight,
FastAPI-inspired web framework with built-in dependency injection,
parameter validation, and automatic type conversion.
"""

import asyncio
import inspect
from functools import partial
from typing import Any, Dict, Type, Union

import msgspec
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from .models import Struct
from .params import Body, Query, Path
from .di import Depends, _registry


class Tachyon:
    """
    Main Tachyon application class.

    Provides a web framework with automatic parameter validation, dependency injection,
    and type conversion. Built on top of Starlette for ASGI compatibility.

    Attributes:
        _router: Internal Starlette application instance
        routes: List of registered routes for introspection
        _instances_cache: Cache for dependency injection singleton instances
    """

    def __init__(self):
        """Initialize a new Tachyon application instance."""
        self._router = Starlette()
        self.routes = []
        self._instances_cache: Dict[Type, Any] = {}

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
        is_path_param: bool = False
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
            if param.name != 'self':
                dependencies[param.name] = self._resolve_dependency(param.annotation)

        # Create instance with resolved dependencies and cache it
        instance = cls(**dependencies)
        self._instances_cache[cls] = instance
        return instance

    def _create_decorator(self, path: str, *, http_method: str):
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

        def decorator(endpoint_func: callable):
            self._add_route(path, endpoint_func, http_method)
            return endpoint_func

        return decorator

    def _add_route(self, path: str, endpoint_func: callable, method: str):
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
                    kwargs_to_inject[param.name] = self._resolve_dependency(target_class)

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
                elif (param.default is inspect.Parameter.empty and
                      param.name in path_params and
                      not is_explicit_dependency and
                      not is_implicit_dependency):
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

            return JSONResponse(payload)

        # Register the route with Starlette
        route = Route(path, endpoint=handler, methods=[method])
        self._router.routes.append(route)
        self.routes.append({"path": path, "method": method, "func": endpoint_func})

    async def __call__(self, scope, receive, send):
        """
        ASGI application entry point.

        Delegates request handling to the internal Starlette application.
        This makes Tachyon compatible with ASGI servers like Uvicorn.
        """
        await self._router(scope, receive, send)
