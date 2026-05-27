# OpenAPI generator — stores the spec state (paths + schemas + config) and
# delegates route operation construction to `RouteOperationBuilder` and HTML
# rendering to the three UI renderers.

from typing import Any, Callable, Dict, Optional

from ._config import OpenAPIConfig
from ._redoc_html import RedocRenderer
from ._route_builder import RouteOperationBuilder
from ._scalar_html import ScalarRenderer
from ._swagger_html import SwaggerUIRenderer


class OpenAPIGenerator:
    """Stores the OpenAPI spec state and delegates building/rendering to collaborators."""

    def __init__(self, config: Optional[OpenAPIConfig] = None) -> None:
        self.config = config or OpenAPIConfig()
        self._openapi_schema: Optional[Dict[str, Any]] = None
        self._route_builder = RouteOperationBuilder(self)
        self._swagger = SwaggerUIRenderer(self.config)
        self._redoc = RedocRenderer(self.config)
        self._scalar = ScalarRenderer(self.config)

    # ── Spec storage ────────────────────────────────────────────────────────

    def get_openapi_schema(self) -> Dict[str, Any]:
        if self._openapi_schema is None:
            self._openapi_schema = self.config.to_openapi_dict()
        return self._openapi_schema

    def add_path(self, path: str, method: str, operation_data: Dict[str, Any]) -> None:
        if self._openapi_schema is None:
            self._openapi_schema = self.config.to_openapi_dict()
        if path not in self._openapi_schema["paths"]:
            self._openapi_schema["paths"][path] = {}
        self._openapi_schema["paths"][path][method.lower()] = operation_data

    def add_schema(self, name: str, schema_data: Dict[str, Any]) -> None:
        if self._openapi_schema is None:
            self._openapi_schema = self.config.to_openapi_dict()
        self._openapi_schema["components"]["schemas"][name] = schema_data

    def generate_route(
        self, path: str, method: str, endpoint_func: Callable, **kwargs: Any
    ) -> None:
        """Introspect endpoint_func and register its OpenAPI operation."""
        operation = self._route_builder.build(path, method, endpoint_func, **kwargs)
        self.add_path(path, method, operation)

    # ── HTML rendering (delegated to per-UI renderer) ───────────────────────

    def get_swagger_ui_html(self, openapi_url: str, title: str) -> str:
        return self._swagger.render(openapi_url, title)

    def get_redoc_html(self, openapi_url: str, title: str) -> str:
        return self._redoc.render(openapi_url, title)

    def get_scalar_html(self, openapi_url: str, title: str) -> str:
        return self._scalar.render(openapi_url, title)
