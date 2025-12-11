from typing import Dict, Any, Optional, List, Type
from dataclasses import dataclass, field
import datetime
import uuid
import json

from .models import Struct
from .utils import TypeUtils, OPENAPI_TYPE_MAP


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
    """Contact information for the API"""

    name: Optional[str] = None
    url: Optional[str] = None
    email: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to OpenAPI contact object"""
        result = {}
        if self.name:
            result["name"] = self.name
        if self.url:
            result["url"] = self.url
        if self.email:
            result["email"] = self.email
        return result


@dataclass
class License:
    """License information for the API"""

    name: str
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to OpenAPI license object"""
        result = {"name": self.name}
        if self.url:
            result["url"] = self.url
        return result


@dataclass
class Info:
    """General information about the API"""

    title: str = "Tachyon API"
    description: Optional[str] = "A fast API built with Tachyon"
    version: str = "0.1.0"
    terms_of_service: Optional[str] = None
    contact: Optional[Contact] = None
    license: Optional[License] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to OpenAPI info object"""
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
    """Server information"""

    url: str
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to OpenAPI server object"""
        result = {"url": self.url}
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class OpenAPIConfig:
    """Configuration for OpenAPI/Swagger documentation"""

    info: Info = field(default_factory=Info)
    servers: List[Server] = field(default_factory=list)
    openapi_version: str = "3.0.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    include_in_schema: bool = True
    # Scalar configuration
    scalar_js_url: str = "https://cdn.jsdelivr.net/npm/@scalar/api-reference"
    scalar_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png"
    # Swagger UI configuration (legacy support)
    swagger_ui_oauth2_redirect_url: Optional[str] = None
    swagger_ui_init_oauth: Optional[Dict[str, Any]] = None
    swagger_ui_parameters: Optional[Dict[str, Any]] = None
    swagger_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png"
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
        """Generate the complete OpenAPI dictionary"""
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
    """Generator for OpenAPI documentation"""

    def __init__(self, config: Optional[OpenAPIConfig] = None):
        """
        Initialize the OpenAPI generator.

        Args:
            config: Optional OpenAPI configuration. Uses defaults if not provided.
        """
        self.config = config or OpenAPIConfig()
        self._openapi_schema: Optional[Dict[str, Any]] = None

    def get_openapi_schema(self) -> Dict[str, Any]:
        """Get the complete OpenAPI schema"""
        if self._openapi_schema is None:
            self._openapi_schema = self.config.to_openapi_dict()
        return self._openapi_schema

    def get_swagger_ui_html(self, openapi_url: str, title: str) -> str:
        """Generate HTML for Swagger UI"""
        swagger_ui_parameters = self.config.swagger_ui_parameters or {}

        # Serialize parameters to JSON safely
        params_json = json.dumps(swagger_ui_parameters)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <link type="text/css" rel="stylesheet" href="{self.config.swagger_css_url}">
    <link rel="shortcut icon" href="{self.config.swagger_favicon_url}">
    <title>{title}</title>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="{self.config.swagger_js_url}"></script>
    <script>
    const ui = SwaggerUIBundle({{
        url: '{openapi_url}',
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
        return html

    def get_redoc_html(self, openapi_url: str, title: str) -> str:
        """Generate HTML for ReDoc"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
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
    <redoc spec-url='{openapi_url}'></redoc>
    <script src="{self.config.redoc_js_url}"></script>
</body>
</html>"""
        return html

    def get_scalar_html(self, openapi_url: str, title: str) -> str:
        """Generate HTML for Scalar API Reference"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
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
        data-url="{openapi_url}"
        src="{self.config.scalar_js_url}"></script>
</body>
</html>"""
        return html

    def add_path(self, path: str, method: str, operation_data: Dict[str, Any]) -> None:
        """
        Add a path operation to the OpenAPI schema.

        Args:
            path: The URL path (e.g., "/items/{item_id}")
            method: HTTP method (e.g., "get", "post")
            operation_data: OpenAPI operation object
        """
        if self._openapi_schema is None:
            self._openapi_schema = self.config.to_openapi_dict()
        if path not in self._openapi_schema["paths"]:
            self._openapi_schema["paths"][path] = {}

        self._openapi_schema["paths"][path][method.lower()] = operation_data

    def add_schema(self, name: str, schema_data: Dict[str, Any]) -> None:
        """
        Add a component schema to the OpenAPI specification.

        Args:
            name: Schema name (e.g., "Item", "User")
            schema_data: OpenAPI schema object
        """
        if self._openapi_schema is None:
            self._openapi_schema = self.config.to_openapi_dict()

        self._openapi_schema["components"]["schemas"][name] = schema_data


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
    # Scalar configuration
    scalar_js_url: str = "https://cdn.jsdelivr.net/npm/@scalar/api-reference",
    scalar_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png",
    # Swagger UI configuration (legacy support)
    swagger_ui_parameters: Optional[Dict[str, Any]] = None,
    swagger_favicon_url: str = "https://fastapi.tiangolo.com/img/favicon.png",
    swagger_js_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
    swagger_css_url: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    redoc_js_url: str = "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
) -> OpenAPIConfig:
    """
    Create a customizable OpenAPI configuration similar to FastAPI.

    Args:
        title: API title
        description: API description
        version: API version
        openapi_version: OpenAPI specification version
        docs_url: URL for Scalar API Reference documentation (default)
        redoc_url: URL for ReDoc documentation
        openapi_url: URL for OpenAPI JSON schema
        contact: Contact information
        license: License information
        servers: List of servers
        terms_of_service: Terms of service URL
        scalar_js_url: Scalar API Reference JavaScript URL
        scalar_favicon_url: Favicon URL for Scalar
        swagger_ui_parameters: Additional Swagger UI parameters
        swagger_favicon_url: Favicon URL for Swagger UI
        swagger_js_url: Swagger UI JavaScript URL
        swagger_css_url: Swagger UI CSS URL
        redoc_js_url: ReDoc JavaScript URL

    Returns:
        Configured OpenAPIConfig instance
    """
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
