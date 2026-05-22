# Top-level OpenAPI configuration — info + servers + docs URLs + UI asset URLs.

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ._info import Info
from ._server import Server


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
