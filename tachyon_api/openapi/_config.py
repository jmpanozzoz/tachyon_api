# OpenAPI configuration — info/servers dataclasses, top-level config, and the
# flat-kwargs convenience factory.

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Contact:
    name: Optional[str] = None
    url: Optional[str] = None
    email: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v
            for k, v in {"name": self.name, "url": self.url, "email": self.email}.items()
            if v
        }


@dataclass
class License:
    name: str
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"name": self.name}
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
        result: Dict[str, Any] = {"url": self.url}
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
    scalar_favicon_url: str = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
        "%3Crect width='32' height='32' rx='7' fill='%23000'/%3E"
        "%3Cline x1='8.5' y1='23.5' x2='23.5' y2='8.5' stroke='%23a78bfa' stroke-width='3.2' stroke-linecap='round'/%3E"
        "%3Cline x1='8.5' y1='8.5' x2='23.5' y2='23.5' stroke='%23f472b6' stroke-width='3.2' stroke-linecap='round'/%3E%3C/svg%3E"
    )
    swagger_ui_parameters: Optional[Dict[str, Any]] = None
    swagger_favicon_url: str = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
        "%3Crect width='32' height='32' rx='7' fill='%23000'/%3E"
        "%3Cline x1='8.5' y1='23.5' x2='23.5' y2='8.5' stroke='%23a78bfa' stroke-width='3.2' stroke-linecap='round'/%3E"
        "%3Cline x1='8.5' y1='8.5' x2='23.5' y2='23.5' stroke='%23f472b6' stroke-width='3.2' stroke-linecap='round'/%3E%3C/svg%3E"
    )
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
        openapi_dict: Dict[str, Any] = {
            "openapi": self.openapi_version,
            "info": self.info.to_dict(),
            "paths": {},
            "components": {"schemas": {}},
        }
        if self.servers:
            openapi_dict["servers"] = [server.to_dict() for server in self.servers]
        return openapi_dict


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
    scalar_js_url: Optional[str] = None,
    scalar_favicon_url: Optional[str] = None,
    swagger_ui_parameters: Optional[Dict[str, Any]] = None,
    swagger_favicon_url: Optional[str] = None,
    swagger_js_url: Optional[str] = None,
    swagger_css_url: Optional[str] = None,
    redoc_js_url: Optional[str] = None,
) -> OpenAPIConfig:
    """Build an OpenAPIConfig from flat parameters (Info is assembled internally)."""
    info = Info(
        title=title,
        description=description,
        version=version,
        terms_of_service=terms_of_service,
        contact=contact,
        license=license,
    )

    # Use config defaults when individual URL overrides are not provided
    defaults = OpenAPIConfig()
    return OpenAPIConfig(
        info=info,
        servers=servers or [],
        openapi_version=openapi_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        scalar_js_url=scalar_js_url or defaults.scalar_js_url,
        scalar_favicon_url=scalar_favicon_url or defaults.scalar_favicon_url,
        swagger_ui_parameters=swagger_ui_parameters,
        swagger_favicon_url=swagger_favicon_url or defaults.swagger_favicon_url,
        swagger_js_url=swagger_js_url or defaults.swagger_js_url,
        swagger_css_url=swagger_css_url or defaults.swagger_css_url,
        redoc_js_url=redoc_js_url or defaults.redoc_js_url,
    )
