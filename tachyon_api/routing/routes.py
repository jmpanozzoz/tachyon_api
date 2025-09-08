"""
Starlette-Native Routes for Tachyon API

This module provides route classes that extend Starlette's routing system
while maintaining Tachyon's functionality for dependency injection and parameter processing.
"""

import inspect
from typing import Any, Callable
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..dependencies.injection import _registry, Depends
from ..processing.parameters import ParameterProcessor, _NotProcessed
from ..processing.responses import ResponseProcessor
from ..dependencies.resolver import DependencyResolver


class TachyonRoute(Route):
    """
    Starlette-native route that encapsulates Tachyon's functionality.

    This route extends Starlette's Route class while providing:
    - Dependency injection
    - Parameter processing (Body, Query, Path)
    - Response processing
    - Error handling

    This makes the routing system more Starlette-compatible while maintaining
    all of Tachyon's features.
    """

    def __init__(
        self,
        path: str,
        endpoint: Callable,
        *,
        methods: list = None,
        name: str = None,
        include_in_schema: bool = True,
        response_model: Any = None,
        dependency_resolver: DependencyResolver = None,
        **kwargs,
    ):
        """
        Initialize a Tachyon route.

        Args:
            path: URL path pattern
            endpoint: Endpoint function
            methods: HTTP methods (defaults to ['GET'])
            name: Route name
            include_in_schema: Whether to include in OpenAPI schema
            response_model: Response model for validation
            dependency_resolver: Dependency resolver instance
            **kwargs: Additional route options
        """
        # Store Tachyon-specific configuration
        self.endpoint = endpoint
        self.response_model = response_model
        self.include_in_schema = include_in_schema
        self._dependency_resolver = dependency_resolver or DependencyResolver()
        self._route_kwargs = kwargs

        # Create the actual handler function
        handler = self._create_handler()

        # Initialize parent Route with our handler
        super().__init__(
            path=path,
            endpoint=handler,
            methods=methods or ["GET"],
            name=name,
        )

    def _create_handler(self) -> Callable:
        """
        Create the async handler function that will be used by Starlette.

        This handler encapsulates all of Tachyon's functionality:
        - Parameter processing
        - Dependency injection
        - Response processing
        - Error handling

        Returns:
            Async handler function compatible with Starlette
        """

        async def handler(request):
            """
            Async request handler that processes parameters and calls the endpoint.

            This handler analyzes the endpoint function signature and automatically
            injects the appropriate values based on parameter annotations and defaults.
            """
            try:
                # Process function signature and inject parameters
                kwargs_to_inject = await self._process_parameters(request)

                # Process the response using ResponseProcessor
                return await ResponseProcessor.process_response(
                    self.endpoint, kwargs_to_inject, self.response_model
                )

            except Exception:
                # Fallback: prevent unhandled exceptions from leaking to the client
                from .responses import internal_server_error_response

                return internal_server_error_response()

        return handler

    async def _process_parameters(self, request) -> dict:
        """
        Process endpoint parameters and inject dependencies.

        Args:
            request: Starlette request object

        Returns:
            Dictionary of parameters to inject into the endpoint function
        """
        kwargs_to_inject = {}
        sig = inspect.signature(self.endpoint)
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
                kwargs_to_inject[param.name] = (
                    self._dependency_resolver.resolve_dependency(target_class)
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
                    raise Exception(
                        "Parameter processing error"
                    )  # Will be caught by handler
                kwargs_to_inject[param.name] = result

        return kwargs_to_inject

    def get_endpoint_info(self) -> dict:
        """
        Get endpoint information for OpenAPI generation and introspection.

        Returns:
            Dictionary with endpoint metadata
        """
        return {
            "path": self.path,
            "method": self.methods[0] if self.methods else "GET",
            "func": self.endpoint,
            "response_model": self.response_model,
            "include_in_schema": self.include_in_schema,
            **self._route_kwargs,
        }


class TachyonRouter:
    """
    Starlette-native router that manages Tachyon routes.

    This router provides a clean interface for registering routes
    while maintaining full compatibility with Starlette's routing system.
    """

    def __init__(self, dependency_resolver: DependencyResolver = None):
        """
        Initialize the Tachyon router.

        Args:
            dependency_resolver: Dependency resolver instance (optional)
        """
        self.routes = []
        self._dependency_resolver = dependency_resolver or DependencyResolver()

    def add_route(
        self,
        path: str,
        endpoint: Callable,
        methods: list = None,
        name: str = None,
        **kwargs,
    ) -> TachyonRoute:
        """
        Add a route to the router.

        Args:
            path: URL path pattern
            endpoint: Endpoint function
            methods: HTTP methods
            name: Route name
            **kwargs: Additional route options

        Returns:
            Created TachyonRoute instance
        """
        route = TachyonRoute(
            path=path,
            endpoint=endpoint,
            methods=methods,
            name=name,
            dependency_resolver=self._dependency_resolver,
            **kwargs,
        )

        self.routes.append(route)
        return route

    def get_starlette_routes(self) -> list:
        """
        Get all routes in Starlette-compatible format.

        Returns:
            List of Starlette Route objects
        """
        return self.routes
