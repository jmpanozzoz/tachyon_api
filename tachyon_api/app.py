"""
Tachyon Web Framework - Main Application Module

This module contains the core Tachyon class that provides a lightweight,
FastAPI-inspired web framework with built-in dependency injection,
parameter validation, and automatic type conversion.
"""

import asyncio
import inspect
import msgspec
import typing
from functools import partial
from typing import Any, Dict, Type, Callable, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from .di import Depends, _registry
from .models import Struct
from .openapi import (
    OpenAPIGenerator,
    OpenAPIConfig,
    create_openapi_config,
)
from .params import Body, Query, Path, Header, Cookie, Form, File
from .exceptions import HTTPException
from .background import BackgroundTasks
from .middlewares.core import (
    apply_middleware_to_router,
    create_decorated_middleware_class,
)
from .responses import (
    HTMLResponse,
    TachyonJSONResponse,
    validation_error_response,
    response_validation_error_response,
    internal_server_error_response,
)
from .utils import TypeConverter, TypeUtils
from .core.lifecycle import LifecycleManager

try:
    from .cache import set_cache_config
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

    def __init__(
        self,
        openapi_config: OpenAPIConfig = None,
        cache_config=None,
        lifespan: Optional[Callable] = None,
    ):
        """
        Initialize a new Tachyon application instance.

        Args:
            openapi_config: Optional OpenAPI configuration. If not provided,
                          uses default configuration similar to FastAPI.
            cache_config: Optional cache configuration (tachyon_api.cache.CacheConfig).
                          If provided, it will be set as the active cache configuration.
            lifespan: Optional async context manager for startup/shutdown events.
                     Similar to FastAPI's lifespan parameter.
        """
        # Lifecycle manager for startup/shutdown events
        self._lifecycle_manager = LifecycleManager(lifespan)

        # Exception handlers registry (exception_type -> handler_function)
        self._exception_handlers: Dict[Type[Exception], Callable] = {}

        # Create combined lifespan that handles both custom lifespan and on_event handlers
        self._router = Starlette(lifespan=self._lifecycle_manager.create_combined_lifespan())
        self.routes = []
        self.middleware_stack = []
        self._instances_cache: Dict[Type, Any] = {}

        # Expose state object for storing app-wide state (like FastAPI)
        self.state = self._router.state

        # Dependency overrides for testing (like FastAPI)
        self.dependency_overrides: Dict[Any, Any] = {}

        # Initialize OpenAPI configuration and generator
        self.openapi_config = openapi_config or create_openapi_config()
        self.openapi_generator = OpenAPIGenerator(self.openapi_config)
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

    def on_event(self, event_type: str):
        """
        Decorator to register startup or shutdown event handlers.

        Args:
            event_type: Either 'startup' or 'shutdown'

        Returns:
            A decorator that registers the handler function

        Example:
            @app.on_event('startup')
            async def on_startup():
                print('Starting up...')

            @app.on_event('shutdown')
            def on_shutdown():
                print('Shutting down...')
        """
        return self._lifecycle_manager.on_event_decorator(event_type)

    def exception_handler(self, exc_class: Type[Exception]):
        """
        Decorator to register a custom exception handler.

        Args:
            exc_class: The exception class to handle

        Returns:
            A decorator that registers the handler function

        Example:
            @app.exception_handler(ValueError)
            async def handle_value_error(request, exc):
                return JSONResponse(
                    status_code=400,
                    content={"error": str(exc)}
                )

            @app.exception_handler(HTTPException)
            async def custom_http_handler(request, exc):
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"error": exc.detail, "custom": True}
                )
        """

        def decorator(func: Callable):
            self._exception_handlers[exc_class] = func
            return func

        return decorator

    def websocket(self, path: str):
        """
        Decorator to register a WebSocket endpoint.

        Args:
            path: URL path pattern for the WebSocket endpoint

        Returns:
            A decorator that registers the WebSocket handler

        Example:
            @app.websocket("/ws")
            async def websocket_endpoint(websocket):
                await websocket.accept()
                data = await websocket.receive_text()
                await websocket.send_text(f"Echo: {data}")
                await websocket.close()

            @app.websocket("/ws/{room_id}")
            async def room_endpoint(websocket, room_id: str):
                await websocket.accept()
                await websocket.send_text(f"Welcome to {room_id}")
                await websocket.close()
        """

        def decorator(func: Callable):
            self._add_websocket_route(path, func)
            return func

        return decorator

    def _add_websocket_route(self, path: str, endpoint_func: Callable):
        """
        Register a WebSocket route with the application.

        Args:
            path: URL path pattern (supports path parameters)
            endpoint_func: The async WebSocket handler function
        """

        async def websocket_handler(websocket: WebSocket):
            # Extract path parameters
            path_params = websocket.path_params

            # Build kwargs for the handler
            kwargs = {"websocket": websocket}

            # Inject path parameters if the handler accepts them
            sig = inspect.signature(endpoint_func)
            for param in sig.parameters.values():
                if param.name != "websocket" and param.name in path_params:
                    kwargs[param.name] = path_params[param.name]

            await endpoint_func(**kwargs)

        route = WebSocketRoute(path, endpoint=websocket_handler)
        self._router.routes.append(route)

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
            - Checks dependency_overrides for test mocking
        """
        # Check for dependency override (for testing)
        if cls in self.dependency_overrides:
            override = self.dependency_overrides[cls]
            # If override is callable, call it to get the instance
            if callable(override) and not isinstance(override, type):
                return override()
            # If it's a class, instantiate it
            elif isinstance(override, type):
                return override()
            # Otherwise return as-is
            return override

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

    async def _resolve_callable_dependency(
        self, dependency: Callable, cache: Dict, request: Request
    ) -> Any:
        """
        Resolve a callable dependency (function, lambda, or class).

        This method calls the dependency function to get its value, supporting
        both sync and async functions. It also handles nested dependencies
        if the callable has parameters with Depends() or Request annotations.

        Args:
            dependency: The callable to invoke
            cache: Per-request cache to avoid calling the same dependency twice
            request: The current request object for injection

        Returns:
            The result of calling the dependency function

        Note:
            - Results are cached per-request to avoid duplicate calls
            - Supports async callables (coroutines)
            - Supports nested Depends() in callable parameters
            - Automatically injects Request when parameter is annotated with Request
        """
        # Check for dependency override (for testing)
        if dependency in self.dependency_overrides:
            override = self.dependency_overrides[dependency]
            # If override is callable, call it
            if callable(override):
                result = override()
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            return override

        # Check cache first (same callable = same result per request)
        if dependency in cache:
            return cache[dependency]

        # Check if the dependency has its own dependencies (nested)
        sig = inspect.signature(dependency)
        nested_kwargs = {}

        for param in sig.parameters.values():
            # Inject Request object if parameter is annotated with Request
            if param.annotation is Request:
                nested_kwargs[param.name] = request
            elif isinstance(param.default, Depends):
                if param.default.dependency is not None:
                    # Nested callable dependency
                    nested_kwargs[param.name] = await self._resolve_callable_dependency(
                        param.default.dependency, cache, request
                    )
                else:
                    # Nested type-based dependency
                    nested_kwargs[param.name] = self._resolve_dependency(
                        param.annotation
                    )

        # Call the dependency (sync or async)
        # Note: asyncio.iscoroutinefunction doesn't work for async __call__ methods,
        # so we check if the result is a coroutine
        result = dependency(**nested_kwargs)
        if asyncio.iscoroutine(result):
            result = await result

        # Cache the result for this request
        cache[dependency] = result
        return result

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
            try:
                kwargs_to_inject = {}
                sig = inspect.signature(endpoint_func)
                query_params = request.query_params
                path_params = request.path_params
                _raw_body = None
                _form_data = None  # Lazy-loaded form data for Form/File params
                # Cache for callable dependencies (same callable = same result per request)
                dependency_cache = {}
                # Background tasks instance (created on demand)
                _background_tasks = None

                # Process each parameter in the endpoint function signature
                for param in sig.parameters.values():
                    # Check for Request object injection
                    # This allows endpoints to receive the raw Starlette Request
                    if param.annotation is Request:
                        kwargs_to_inject[param.name] = request
                        continue

                    # Check for BackgroundTasks injection
                    if param.annotation is BackgroundTasks:
                        if _background_tasks is None:
                            _background_tasks = BackgroundTasks()
                        kwargs_to_inject[param.name] = _background_tasks
                        continue

                    # Determine if this parameter is a dependency
                    is_explicit_dependency = isinstance(param.default, Depends)
                    is_implicit_dependency = (
                        param.default is inspect.Parameter.empty
                        and param.annotation in _registry
                    )

                    # Process dependencies (explicit and implicit)
                    if is_explicit_dependency or is_implicit_dependency:
                        if (
                            is_explicit_dependency
                            and param.default.dependency is not None
                        ):
                            # Depends(callable) - call the factory function
                            resolved = await self._resolve_callable_dependency(
                                param.default.dependency, dependency_cache, request
                            )
                            kwargs_to_inject[param.name] = resolved
                        else:
                            # Depends() or implicit - resolve by type annotation
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
                            # Attempt to build field errors map using e.path
                            field_errors = None
                            try:
                                path = getattr(e, "path", None)
                                if path:
                                    # Choose last string-ish path element as field name
                                    field_name = None
                                    for p in reversed(path):
                                        if isinstance(p, str):
                                            field_name = p
                                            break
                                    if field_name:
                                        field_errors = {field_name: [str(e)]}
                            except Exception:
                                field_errors = None
                            return validation_error_response(
                                str(e), errors=field_errors
                            )

                    # Process Query parameters (URL query string)
                    elif isinstance(param.default, Query):
                        query_info = param.default
                        param_name = param.name

                        # Determine typing for advanced cases
                        ann = param.annotation
                        origin = typing.get_origin(ann)
                        args = typing.get_args(ann)

                        # List[T] handling
                        if origin in (list, typing.List):
                            item_type = args[0] if args else str
                            values = []
                            # collect repeated params
                            if hasattr(query_params, "getlist"):
                                values = query_params.getlist(param_name)
                            # if not repeated, check for CSV in single value
                            if not values and param_name in query_params:
                                raw = query_params[param_name]
                                values = raw.split(",") if "," in raw else [raw]
                            # flatten CSV in any element
                            flat_values = []
                            for v in values:
                                if isinstance(v, str) and "," in v:
                                    flat_values.extend(v.split(","))
                                else:
                                    flat_values.append(v)
                            values = flat_values
                            if not values:
                                if query_info.default is not ...:
                                    kwargs_to_inject[param_name] = query_info.default
                                    continue
                                return validation_error_response(
                                    f"Missing required query parameter: {param_name}"
                                )
                            # Unwrap Optional for item type
                            base_item_type, item_is_opt = TypeUtils.unwrap_optional(
                                item_type
                            )
                            converted_list = []
                            for v in values:
                                if item_is_opt and (v == "" or v.lower() == "null"):
                                    converted_list.append(None)
                                    continue
                                converted_value = TypeConverter.convert_value(
                                    v, base_item_type, param_name, is_path_param=False
                                )
                                if isinstance(converted_value, JSONResponse):
                                    return converted_value
                                converted_list.append(converted_value)
                            kwargs_to_inject[param_name] = converted_list
                            continue

                        # Optional[T] handling for single value
                        base_type, _is_opt = TypeUtils.unwrap_optional(ann)

                        if param_name in query_params:
                            value_str = query_params[param_name]
                            converted_value = TypeConverter.convert_value(
                                value_str, base_type, param_name, is_path_param=False
                            )
                            if isinstance(converted_value, JSONResponse):
                                return converted_value
                            kwargs_to_inject[param_name] = converted_value

                        elif query_info.default is not ...:
                            kwargs_to_inject[param.name] = query_info.default
                        else:
                            return validation_error_response(
                                f"Missing required query parameter: {param_name}"
                            )

                    # Process Header parameters
                    elif isinstance(param.default, Header):
                        header_info = param.default
                        # Use alias if provided, otherwise convert param name
                        # Python uses underscores, HTTP uses hyphens
                        if header_info.alias:
                            header_name = header_info.alias.lower()
                        else:
                            header_name = param.name.replace("_", "-").lower()

                        # Get header value (case-insensitive)
                        header_value = request.headers.get(header_name)

                        if header_value is not None:
                            kwargs_to_inject[param.name] = header_value
                        elif header_info.default is not ...:
                            kwargs_to_inject[param.name] = header_info.default
                        else:
                            return validation_error_response(
                                f"Missing required header: {header_name}"
                            )

                    # Process Cookie parameters
                    elif isinstance(param.default, Cookie):
                        cookie_info = param.default
                        # Use alias if provided, otherwise use param name
                        cookie_name = cookie_info.alias or param.name

                        # Get cookie value
                        cookie_value = request.cookies.get(cookie_name)

                        if cookie_value is not None:
                            kwargs_to_inject[param.name] = cookie_value
                        elif cookie_info.default is not ...:
                            kwargs_to_inject[param.name] = cookie_info.default
                        else:
                            return validation_error_response(
                                f"Missing required cookie: {cookie_name}"
                            )

                    # Process Form parameters (form data)
                    elif isinstance(param.default, Form):
                        # Parse form data if not already done
                        if _form_data is None:
                            _form_data = await request.form()

                        form_info = param.default
                        field_name = form_info.alias or param.name

                        if field_name in _form_data:
                            kwargs_to_inject[param.name] = _form_data[field_name]
                        elif form_info.default is not ...:
                            kwargs_to_inject[param.name] = form_info.default
                        else:
                            return validation_error_response(
                                f"Missing required form field: {field_name}"
                            )

                    # Process File parameters (file uploads)
                    elif isinstance(param.default, File):
                        # Parse form data if not already done
                        if _form_data is None:
                            _form_data = await request.form()

                        file_info = param.default
                        field_name = param.name

                        if field_name in _form_data:
                            uploaded_file = _form_data[field_name]
                            # Check if it's actually a file (UploadFile)
                            if hasattr(uploaded_file, "filename"):
                                kwargs_to_inject[param.name] = uploaded_file
                            elif file_info.default is not ...:
                                kwargs_to_inject[param.name] = file_info.default
                            else:
                                return validation_error_response(
                                    f"Invalid file upload for: {field_name}"
                                )
                        elif file_info.default is not ...:
                            kwargs_to_inject[param.name] = file_info.default
                        else:
                            return validation_error_response(
                                f"Missing required file: {field_name}"
                            )

                    # Process explicit Path parameters (with Path() annotation)
                    elif isinstance(param.default, Path):
                        param_name = param.name
                        if param_name in path_params:
                            value_str = path_params[param_name]
                            # Support List[T] in path params via CSV
                            ann = param.annotation
                            origin = typing.get_origin(ann)
                            args = typing.get_args(ann)
                            if origin in (list, typing.List):
                                item_type = args[0] if args else str
                                parts = value_str.split(",") if value_str else []
                                # Unwrap Optional for item type
                                base_item_type, item_is_opt = TypeUtils.unwrap_optional(
                                    item_type
                                )
                                converted_list = []
                                for v in parts:
                                    if item_is_opt and (v == "" or v.lower() == "null"):
                                        converted_list.append(None)
                                        continue
                                    converted_value = TypeConverter.convert_value(
                                        v,
                                        base_item_type,
                                        param_name,
                                        is_path_param=True,
                                    )
                                    if isinstance(converted_value, JSONResponse):
                                        return converted_value
                                    converted_list.append(converted_value)
                                kwargs_to_inject[param_name] = converted_list
                            else:
                                converted_value = TypeConverter.convert_value(
                                    value_str, ann, param_name, is_path_param=True
                                )
                                # Return 404 if conversion failed
                                if isinstance(converted_value, JSONResponse):
                                    return converted_value
                                kwargs_to_inject[param_name] = converted_value
                        else:
                            return JSONResponse(
                                {"detail": "Not Found"}, status_code=404
                            )

                    # Process implicit Path parameters (URL path variables without Path())
                    elif (
                        param.default is inspect.Parameter.empty
                        and param.name in path_params
                        and not is_explicit_dependency
                        and not is_implicit_dependency
                    ):
                        param_name = param.name
                        value_str = path_params[param_name]
                        # Support List[T] via CSV
                        ann = param.annotation
                        origin = typing.get_origin(ann)
                        args = typing.get_args(ann)
                        if origin in (list, typing.List):
                            item_type = args[0] if args else str
                            parts = value_str.split(",") if value_str else []
                            # Unwrap Optional for item type
                            base_item_type, item_is_opt = TypeUtils.unwrap_optional(
                                item_type
                            )
                            converted_list = []
                            for v in parts:
                                if item_is_opt and (v == "" or v.lower() == "null"):
                                    converted_list.append(None)
                                    continue
                                converted_value = TypeConverter.convert_value(
                                    v, base_item_type, param_name, is_path_param=True
                                )
                                if isinstance(converted_value, JSONResponse):
                                    return converted_value
                                converted_list.append(converted_value)
                            kwargs_to_inject[param_name] = converted_list
                        else:
                            converted_value = TypeConverter.convert_value(
                                value_str, ann, param_name, is_path_param=True
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

                # Run background tasks if any were registered
                if _background_tasks is not None:
                    await _background_tasks.run_tasks()

                # If the endpoint already returned a Response object, return it directly
                if isinstance(payload, Response):
                    return payload

                # Validate/convert response against response_model if provided
                if response_model is not None:
                    try:
                        payload = msgspec.convert(payload, response_model)
                    except Exception as e:
                        return response_validation_error_response(str(e))

                # Convert Struct objects to dictionaries for JSON serialization
                if isinstance(payload, Struct):
                    payload = msgspec.to_builtins(payload)
                elif isinstance(payload, dict):
                    # Convert any Struct values in the dictionary
                    for key, value in payload.items():
                        if isinstance(value, Struct):
                            payload[key] = msgspec.to_builtins(value)

                return TachyonJSONResponse(payload)

            except HTTPException as exc:
                # Handle HTTPException - check for custom handler first
                handler = self._exception_handlers.get(HTTPException)
                if handler is not None:
                    if asyncio.iscoroutinefunction(handler):
                        return await handler(request, exc)
                    else:
                        return handler(request, exc)
                # Default HTTPException handling
                response = JSONResponse(
                    {"detail": exc.detail}, status_code=exc.status_code
                )
                if exc.headers:
                    for key, value in exc.headers.items():
                        response.headers[key] = value
                return response

            except Exception as exc:
                # Check for custom exception handler
                for exc_class, handler in self._exception_handlers.items():
                    if isinstance(exc, exc_class):
                        if asyncio.iscoroutinefunction(handler):
                            return await handler(request, exc)
                        else:
                            return handler(request, exc)
                # Fallback: prevent unhandled exceptions from leaking to the client
                return internal_server_error_response()

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

        # Ensure common error schemas exist in components
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
                        "additionalProperties": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
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
                },
                "422": {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ValidationErrorResponse"
                            }
                        }
                    },
                },
                "500": {
                    "description": "Response Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ResponseValidationError"
                            }
                        }
                    },
                },
            },
        }

        # If a response_model is provided and is a Struct, use it for the 200 response schema
        response_model = kwargs.get("response_model")
        if response_model is not None and issubclass(response_model, Struct):
            from .openapi import build_components_for_struct

            comps = build_components_for_struct(response_model)
            for name, schema in comps.items():
                self.openapi_generator.add_schema(name, schema)
            operation["responses"]["200"]["content"]["application/json"]["schema"] = {
                "$ref": f"#/components/schemas/{response_model.__name__}"
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
                        "schema": self._build_param_openapi_schema(param.annotation),
                        "description": getattr(param.default, "description", ""),
                    }
                )

            # Process header parameters
            elif isinstance(param.default, Header):
                parameters.append(
                    {
                        "name": param.name,
                        "in": "header",
                        "required": param.default.default is ...,
                        "schema": self._build_param_openapi_schema(param.annotation),
                        "description": getattr(param.default, "description", ""),
                    }
                )

            # Process cookie parameters
            elif isinstance(param.default, Cookie):
                parameters.append(
                    {
                        "name": param.name,
                        "in": "cookie",
                        "required": param.default.default is ...,
                        "schema": self._build_param_openapi_schema(param.annotation),
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
                        "schema": self._build_param_openapi_schema(param.annotation),
                        "description": getattr(param.default, "description", "")
                        if isinstance(param.default, Path)
                        else "",
                    }
                )

            # Process body parameters
            elif isinstance(param.default, Body):
                model_class = param.annotation
                if issubclass(model_class, Struct):
                    from .openapi import build_components_for_struct

                    comps = build_components_for_struct(model_class)
                    for name, schema in comps.items():
                        self.openapi_generator.add_schema(name, schema)

                    request_body_schema = {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": f"#/components/schemas/{model_class.__name__}"
                                }
                            }
                        },
                        "required": True,
                    }

        # Add parameters to operation if any exist
        if parameters:
            operation["parameters"] = parameters

        if request_body_schema:
            operation["requestBody"] = request_body_schema

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
    def _build_param_openapi_schema(python_type: Type) -> Dict[str, Any]:
        """Build OpenAPI schema for parameter types, supporting Optional[T] and List[T]."""
        # Use centralized TypeUtils for type checking
        inner_type, nullable = TypeUtils.unwrap_optional(python_type)

        # Check if it's a List type
        is_list, item_type = TypeUtils.is_list_type(inner_type)
        if is_list:
            # Check if item type is Optional
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

            # Check if it's a WebSocket route
            if route_info.get("is_websocket"):
                self._add_websocket_route(full_path, route_info["func"])
                continue

            # Create a copy of route info with the full path
            route_kwargs = route_info.copy()
            route_kwargs.pop("path", None)
            route_kwargs.pop("method", None)
            route_kwargs.pop("func", None)
            route_kwargs.pop("is_websocket", None)

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
        # Use centralized helper to apply middleware to internal Starlette app
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
            # Create a middleware class from the decorated function
            DecoratedMiddleware = create_decorated_middleware_class(
                middleware_func, middleware_type
            )
            # Register the middleware using the existing method
            self.add_middleware(DecoratedMiddleware)
            return middleware_func

        return decorator
