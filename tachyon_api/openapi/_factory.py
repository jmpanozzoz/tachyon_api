# Convenience factory for building an OpenAPIConfig from flat kwargs.

from typing import Any, Dict, List, Optional

from ._config import OpenAPIConfig
from ._info import Contact, Info, License
from ._server import Server


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
