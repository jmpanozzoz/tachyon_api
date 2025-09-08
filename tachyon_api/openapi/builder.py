"""
OpenAPI Documentation Builder for Tachyon API

This module handles the generation and management of OpenAPI documentation
for the Tachyon framework, including schema generation, parameter processing,
and documentation endpoint setup.
"""

import inspect
from typing import Any, Dict, Type, Union, Callable
from starlette.responses import HTMLResponse

from ..schemas.models import Struct
from ..schemas.parameters import Body, Query, Path
from .schema import (
    OpenAPIGenerator,
    OpenAPIConfig,
    build_components_for_struct,
)


class OpenAPIBuilder:
    """
    Handles OpenAPI documentation generation and management.

    This class centralizes all OpenAPI-related functionality, including
    schema generation, parameter processing, and documentation endpoint setup.
    """

    def __init__(
        self, openapi_config: OpenAPIConfig, openapi_generator: OpenAPIGenerator
    ):
        """
        Initialize the OpenAPI builder.

        Args:
            openapi_config: OpenAPI configuration
            openapi_generator: OpenAPI generator instance
        """
        self.openapi_config = openapi_config
        self.openapi_generator = openapi_generator

    def generate_openapi_for_route(
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
            if isinstance(
                param.default, (Body.__class__, Query.__class__, Path.__class__)
            ) or (
                param.default is inspect.Parameter.empty
                and param.annotation.__name__ in ["Depends"]
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
    def _get_openapi_type(python_type: Type) -> str:
        """Convert Python type to OpenAPI schema type."""
        type_map: Dict[Type, str] = {
            int: "integer",
            str: "string",
            bool: "boolean",
            float: "number",
        }
        return type_map.get(python_type, "string")

    @staticmethod
    def _build_param_openapi_schema(python_type: Type) -> Dict[str, Any]:
        """Build OpenAPI schema for parameter types, supporting Optional[T] and List[T]."""
        import typing

        origin = typing.get_origin(python_type)
        args = typing.get_args(python_type)
        nullable = False
        # Optional[T]
        if origin is Union and args:
            non_none = [a for a in args if a is not type(None)]  # noqa: E721
            if len(non_none) == 1:
                python_type = non_none[0]
                nullable = True
        # List[T] (and List[Optional[T]])
        origin = typing.get_origin(python_type)
        args = typing.get_args(python_type)
        if origin in (list, typing.List):
            item_type = args[0] if args else str
            # Unwrap Optional in items for List[Optional[T]]
            item_origin = typing.get_origin(item_type)
            item_args = typing.get_args(item_type)
            item_nullable = False
            if item_origin is Union and item_args:
                item_non_none = [a for a in item_args if a is not type(None)]  # noqa: E721
                if len(item_non_none) == 1:
                    item_type = item_non_none[0]
                    item_nullable = True
            schema = {
                "type": "array",
                "items": {"type": OpenAPIBuilder._get_openapi_type(item_type)},
            }
            if item_nullable:
                schema["items"]["nullable"] = True
        else:
            schema = {"type": OpenAPIBuilder._get_openapi_type(python_type)}
        if nullable:
            schema["nullable"] = True
        return schema

    def setup_docs(self, app):
        """
        Setup OpenAPI documentation endpoints.

        This method registers the routes for serving OpenAPI JSON schema,
        Swagger UI, and ReDoc documentation interfaces.

        Args:
            app: The Tachyon application instance
        """

        # OpenAPI JSON schema endpoint
        @app.get(self.openapi_config.openapi_url, include_in_schema=False)
        def get_openapi_schema():
            """Serve the OpenAPI JSON schema."""
            return self.openapi_generator.get_openapi_schema()

        # Scalar API Reference documentation endpoint (default for /docs)
        @app.get(self.openapi_config.docs_url, include_in_schema=False)
        def get_scalar_docs():
            """Serve the Scalar API Reference documentation interface."""
            html = self.openapi_generator.get_scalar_html(
                self.openapi_config.openapi_url, self.openapi_config.info.title
            )
            return HTMLResponse(html)

        # Swagger UI documentation endpoint (legacy support)
        @app.get("/swagger", include_in_schema=False)
        def get_swagger_ui():
            """Serve the Swagger UI documentation interface."""
            html = self.openapi_generator.get_swagger_ui_html(
                self.openapi_config.openapi_url, self.openapi_config.info.title
            )
            return HTMLResponse(html)

        # ReDoc documentation endpoint
        @app.get(self.openapi_config.redoc_url, include_in_schema=False)
        def get_redoc():
            """Serve the ReDoc documentation interface."""
            html = self.openapi_generator.get_redoc_html(
                self.openapi_config.openapi_url, self.openapi_config.info.title
            )
            return HTMLResponse(html)
