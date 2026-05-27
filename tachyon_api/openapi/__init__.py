"""OpenAPI spec generation, configuration dataclasses, and HTML doc renderers."""

# Configuration dataclasses
from ._config import OpenAPIConfig
from ._factory import create_openapi_config
from ._info import Contact, Info, License
from ._server import Server

# Generator + builders
from ._generator import OpenAPIGenerator
from ._param_schemas import build_param_schema
from ._struct_schemas import (
    _generate_struct_schema,
    _schema_for_python_type,
    build_components_for_struct,
)

__all__ = [
    "Contact",
    "Info",
    "License",
    "Server",
    "OpenAPIConfig",
    "create_openapi_config",
    "OpenAPIGenerator",
    "build_param_schema",
    "build_components_for_struct",
]
