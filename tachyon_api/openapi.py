from enum import Enum
from typing import Dict, Any, Optional, List, Type, Callable
from dataclasses import dataclass, field
import datetime
import html
import inspect
import uuid
import json

from .models import Struct
from .utils import TypeUtils, OPENAPI_TYPE_MAP

# Types that map to a specific OpenAPI string format
_OPENAPI_FORMAT_MAP: Dict[Type, tuple] = {
    datetime.datetime: ("string", "date-time"),
    datetime.date:     ("string", "date"),
    uuid.UUID:         ("string", "uuid"),
}


def _safe_json(value: Any) -> str:
    """JSON-encode a value safe for embedding inside a <script> tag.
    Escapes <, >, and & so browsers cannot interpret them as HTML tags."""
    return (
        json.dumps(value, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _schema_for_python_type(
    py_type: Type,
    components: Dict[str, Dict[str, Any]],
    visited: set[Type],
) -> Dict[str, Any]:
    """Return OpenAPI schema for a Python type, adding components for Structs if needed."""
    # Check if Optional[T] using centralized utility
    inner_type, is_optional = TypeUtils.unwrap_optional(py_type)
    if is_optional:
        schema = _schema_for_python_type(inner_type, components, visited)
        schema["nullable"] = True
        return schema

    # Check if List[T] using centralized utility
    is_list, item_type = TypeUtils.is_list_type(py_type)
    if is_list:
        item_schema = _schema_for_python_type(item_type, components, visited)
        return {"type": "array", "items": item_schema}

    # Struct subclass
    if isinstance(py_type, type) and issubclass(py_type, Struct):
        name = py_type.__name__
        if py_type not in visited:
            visited.add(py_type)
            components[name] = _generate_struct_schema(py_type, components, visited)
        return {"$ref": f"#/components/schemas/{name}"}

    # Special formats
    if py_type is uuid.UUID:
        return {"type": "string", "format": "uuid"}
    if py_type is datetime.datetime:
        return {"type": "string", "format": "date-time"}
    if py_type is datetime.date:
        return {"type": "string", "format": "date"}

    # Scalars - use centralized type mapping
    return {"type": OPENAPI_TYPE_MAP.get(py_type, "string")}


def _generate_struct_schema(
    struct_class: Type[Struct],
    components: Dict[str, Dict[str, Any]],
    visited: set[Type],
) -> Dict[str, Any]:
    """
    Generate a JSON Schema dictionary for a msgspec Struct, populating components for nested Structs.
    """
    properties: Dict[str, Any] = {}
    required: List[str] = []

    annotations = getattr(struct_class, "__annotations__", {})
    for field_name in getattr(struct_class, "__struct_fields__", annotations.keys()):
        field_type = annotations.get(field_name, str)
        # Use centralized TypeUtils instead of local _unwrap_optional
        base_type, is_opt = TypeUtils.unwrap_optional(field_type)

        # Build property schema
        prop_schema = _schema_for_python_type(base_type, components, visited)
        if is_opt:
            prop_schema["nullable"] = True

        properties[field_name] = prop_schema

        # Determine required: mark non-Optional fields as required
        if not is_opt:
            required.append(field_name)

    schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def build_components_for_struct(
    struct_class: Type[Struct],
) -> Dict[str, Dict[str, Any]]:
    """
    Build components schemas for the given Struct and all nested Structs.

    Returns a dict mapping component name to schema, including the top-level struct.
    """
    components: Dict[str, Dict[str, Any]] = {}
    visited: set[Type] = set()
    name = struct_class.__name__
    components[name] = _generate_struct_schema(struct_class, components, visited)
    return components


@dataclass
class Contact:
    name: Optional[str] = None
    url: Optional[str] = None
    email: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in {"name": self.name, "url": self.url, "email": self.email}.items() if v}


@dataclass
class License:
    name: str
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"name": self.name}
        if self.url:
            result["url"] = self.url
        return result


@dataclass
class Info:
    title: str = "Tachyon API"
    description: Optional[str] = "A fast API built with Tachyon"
    version: str = "0.1.0"
    terms_of_service: Optional[str] = None
    contact: Optional[Contact] = None
    license: Optional[License] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"title": self.title, "version": self.version}
        if self.description:
            result["description"] = self.description
        if self.terms_of_service:
            result["termsOfService"] = self.terms_of_service
        if self.contact:
            result["contact"] = self.contact.to_dict()
        if self.license:
            result["license"] = self.license.to_dict()
        return result


@dataclass
class Server:
    url: str
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"url": self.url}
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class OpenAPIConfig:
    info: Info = field(default_factory=Info)
    servers: List[Server] = field(default_factory=list)
    openapi_version: str = "3.0.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    scalar_js_url: str = "https://cdn.jsdelivr.net/npm/@scalar/api-reference"
    scalar_favicon_url: str = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23000'/%3E%3Cline x1='8.5' y1='23.5' x2='23.5' y2='8.5' stroke='%23a78bfa' stroke-width='3.2' stroke-linecap='round'/%3E%3Cline x1='8.5' y1='8.5' x2='23.5' y2='23.5' stroke='%23f472b6' stroke-width='3.2' stroke-linecap='round'/%3E%3C/svg%3E"
    swagger_ui_parameters: Optional[Dict[str, Any]] = None
    swagger_favicon_url: str = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23000'/%3E%3Cline x1='8.5' y1='23.5' x2='23.5' y2='8.5' stroke='%23a78bfa' stroke-width='3.2' stroke-linecap='round'/%3E%3Cline x1='8.5' y1='8.5' x2='23.5' y2='23.5' stroke='%23f472b6' stroke-width='3.2' stroke-linecap='round'/%3E%3C/svg%3E"
    swagger_js_url: str = (
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
    )
    swagger_css_url: str = (
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
    )
    redoc_js_url: str = (
        "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"
    )

    def to_openapi_dict(self) -> Dict[str, Any]:
        openapi_dict = {
            "openapi": self.openapi_version,
            "info": self.info.to_dict(),
            "paths": {},
            "components": {"schemas": {}},
        }
        if self.servers:
            openapi_dict["servers"] = [server.to_dict() for server in self.servers]
        return openapi_dict


class OpenAPIGenerator:
    def __init__(self, config: Optional[OpenAPIConfig] = None):
        self.config = config or OpenAPIConfig()
        self._openapi_schema: Optional[Dict[str, Any]] = None

    def get_openapi_schema(self) -> Dict[str, Any]:
        if self._openapi_schema is None:
            self._openapi_schema = self.config.to_openapi_dict()
        return self._openapi_schema

    def get_swagger_ui_html(self, openapi_url: str, title: str) -> str:
        """Generate HTML for Swagger UI"""
        swagger_ui_parameters = self.config.swagger_ui_parameters or {}
        params_json = _safe_json(swagger_ui_parameters)
        safe_url = _safe_json(openapi_url)
        safe_title = html.escape(title)

        return f"""<!DOCTYPE html>
<html>
<head>
    <link type="text/css" rel="stylesheet" href="{self.config.swagger_css_url}">
    <link rel="shortcut icon" href="{self.config.swagger_favicon_url}">
    <title>{safe_title}</title>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="{self.config.swagger_js_url}"></script>
    <script>
    const ui = SwaggerUIBundle({{
        url: {safe_url},
        dom_id: '#swagger-ui',
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIBundle.presets.standalone
        ],
        layout: "BaseLayout",
        ...{params_json}
    }})
    </script>
</body>
</html>"""

    def get_redoc_html(self, openapi_url: str, title: str) -> str:
        """Generate HTML for ReDoc"""
        safe_url = html.escape(openapi_url, quote=True)
        safe_title = html.escape(title)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{safe_title}</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
    body {{
        margin: 0;
        padding: 0;
    }}
    </style>
</head>
<body>
    <redoc spec-url='{safe_url}'></redoc>
    <script src="{self.config.redoc_js_url}"></script>
</body>
</html>"""

    def get_scalar_html(self, openapi_url: str, title: str) -> str:
        """Generate HTML for Scalar API Reference"""
        safe_url = html.escape(openapi_url, quote=True)
        safe_title = html.escape(title)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{safe_title}</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="shortcut icon" href="{self.config.scalar_favicon_url}">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <script
        id="api-reference"
        data-url="{safe_url}"
        src="{self.config.scalar_js_url}"></script>
</body>
</html>"""

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

    def generate_route(self, path: str, method: str, endpoint_func: Callable, **kwargs: Any) -> None:
        """Introspect endpoint_func and register its OpenAPI operation."""
        from .params import Body, Query, Path, Header, Cookie
        from .di import Depends, _registry

        sig = inspect.signature(endpoint_func)
        operation: Dict[str, Any] = {
            "summary": kwargs.get("summary", _summary_from_func(endpoint_func)),
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
            is_struct = (
                response_model is not None
                and isinstance(response_model, type)
                and issubclass(response_model, Struct)
            )
        except TypeError:
            is_struct = False
        if is_struct:
            for name, schema in build_components_for_struct(response_model).items():
                self.add_schema(name, schema)
            operation["responses"]["200"]["content"]["application/json"]["schema"] = {
                "$ref": f"#/components/schemas/{response_model.__name__}"
            }

        if "tags" in kwargs:
            operation["tags"] = kwargs["tags"]

        _PARAM_IN = {Query: "query", Header: "header", Cookie: "cookie"}
        parameters: List[Dict[str, Any]] = []
        request_body_schema = None

        for param in sig.parameters.values():
            if isinstance(param.default, Depends) or (
                param.default is inspect.Parameter.empty and param.annotation in _registry
            ):
                continue

            for param_cls, location in _PARAM_IN.items():
                if isinstance(param.default, param_cls):
                    parameters.append({
                        "name": param.name,
                        "in": location,
                        "required": param.default.default is ...,
                        "schema": build_param_schema(param.annotation),
                        "description": getattr(param.default, "description", ""),
                    })
                    break
            else:
                if isinstance(param.default, Path) or f"{{{param.name}}}" in path:
                    parameters.append({
                        "name": param.name,
                        "in": "path",
                        "required": True,
                        "schema": build_param_schema(param.annotation),
                        "description": getattr(param.default, "description", "") if isinstance(param.default, Path) else "",
                    })
                elif (
                    isinstance(param.default, Body)
                    and isinstance(param.annotation, type)
                    and issubclass(param.annotation, Struct)
                ):
                    for name, schema in build_components_for_struct(param.annotation).items():
                        self.add_schema(name, schema)
                    request_body_schema = {
                        "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{param.annotation.__name__}"}}},
                        "required": True,
                    }

        if parameters:
            operation["parameters"] = parameters
        if request_body_schema:
            operation["requestBody"] = request_body_schema

        self.add_path(path, method, operation)


def _scalar_schema(t: Type) -> Dict[str, Any]:
    fmt = _OPENAPI_FORMAT_MAP.get(t)
    if fmt:
        return {"type": fmt[0], "format": fmt[1]}
    if isinstance(t, type) and issubclass(t, Enum):
        members = [e.value for e in t]
        val_type = "integer" if members and all(isinstance(v, int) for v in members) else "string"
        return {"type": val_type, "enum": members}
    return {"type": TypeUtils.get_openapi_type(t)}


def build_param_schema(python_type: Type) -> Dict[str, Any]:
    """Build an OpenAPI schema for a scalar, list, optional, enum, or formatted type."""
    inner_type, nullable = TypeUtils.unwrap_optional(python_type)
    is_list, item_type = TypeUtils.is_list_type(inner_type)
    if is_list:
        base_item_type, item_nullable = TypeUtils.unwrap_optional(item_type)
        item_schema = _scalar_schema(base_item_type)
        if item_nullable:
            item_schema["nullable"] = True
        schema: Dict[str, Any] = {"type": "array", "items": item_schema}
    else:
        schema = _scalar_schema(inner_type)
    if nullable:
        schema["nullable"] = True
    return schema


def _summary_from_func(func: Callable) -> str:
    return func.__name__.replace("_", " ").title()


def create_openapi_config(
    title: str = "Tachyon API",
    description: Optional[str] = "A fast API built with Tachyon",
    version: str = "0.1.0",
    openapi_version: str = "3.0.0",
    docs_url: str = "/docs",
    redoc_url: str = "/redoc",
    openapi_url: str = "/openapi.json",
    contact: Optional[Contact] = None,
    license: Optional[License] = None,
    servers: Optional[List[Server]] = None,
    terms_of_service: Optional[str] = None,
    scalar_js_url: str = "https://cdn.jsdelivr.net/npm/@scalar/api-reference",
    scalar_favicon_url: str = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23000'/%3E%3Cline x1='8.5' y1='23.5' x2='23.5' y2='8.5' stroke='%23a78bfa' stroke-width='3.2' stroke-linecap='round'/%3E%3Cline x1='8.5' y1='8.5' x2='23.5' y2='23.5' stroke='%23f472b6' stroke-width='3.2' stroke-linecap='round'/%3E%3C/svg%3E",
    swagger_ui_parameters: Optional[Dict[str, Any]] = None,
    swagger_favicon_url: str = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23000'/%3E%3Cline x1='8.5' y1='23.5' x2='23.5' y2='8.5' stroke='%23a78bfa' stroke-width='3.2' stroke-linecap='round'/%3E%3Cline x1='8.5' y1='8.5' x2='23.5' y2='23.5' stroke='%23f472b6' stroke-width='3.2' stroke-linecap='round'/%3E%3C/svg%3E",
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    redoc_js_url: str = "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
) -> OpenAPIConfig:
    info = Info(
        title=title,
        description=description,
        version=version,
        terms_of_service=terms_of_service,
        contact=contact,
        license=license,
    )

    return OpenAPIConfig(
        info=info,
        servers=servers or [],
        openapi_version=openapi_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        scalar_js_url=scalar_js_url,
        scalar_favicon_url=scalar_favicon_url,
        swagger_ui_parameters=swagger_ui_parameters,
        swagger_favicon_url=swagger_favicon_url,
        swagger_js_url=swagger_js_url,
        swagger_css_url=swagger_css_url,
        redoc_js_url=redoc_js_url,
    )
