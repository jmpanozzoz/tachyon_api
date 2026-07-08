"""OpenAPI spec generation, configuration dataclasses, and HTML doc renderers."""

# Configuration dataclasses
from ._config import (
    Contact,
    Info,
    License,
    OpenAPIConfig,
    Server,
    create_openapi_config,
)

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
