# Schema generation for msgspec Structs — recursive with $ref components for nested types.
#
# `_schema_for_python_type` is also used for `response_model` and `Body` annotations
# in `RouteOperationBuilder`, so it accepts any Python type (list, optional, scalar)
# and falls back to `OPENAPI_TYPE_MAP` for unknown primitives.

import datetime
import uuid
from typing import Any, Dict, List, Set, Type

from ..models import Struct
from ..utils import OPENAPI_TYPE_MAP, TypeUtils


def _schema_for_python_type(
    py_type: Type,
    components: Dict[str, Dict[str, Any]],
    visited: Set[Type],
) -> Dict[str, Any]:
    """Return OpenAPI schema for a Python type; adds components for Structs encountered."""
    inner_type, is_optional = TypeUtils.unwrap_optional(py_type)
    if is_optional:
        schema = _schema_for_python_type(inner_type, components, visited)
        schema["nullable"] = True
        return schema

    is_list, item_type = TypeUtils.is_list_type(py_type)
    if is_list:
        item_schema = _schema_for_python_type(item_type, components, visited)
        return {"type": "array", "items": item_schema}

    if isinstance(py_type, type) and issubclass(py_type, Struct):
        name = py_type.__name__
        if py_type not in visited:
            visited.add(py_type)
            components[name] = _generate_struct_schema(py_type, components, visited)
        return {"$ref": f"#/components/schemas/{name}"}

    if py_type is uuid.UUID:
        return {"type": "string", "format": "uuid"}
    if py_type is datetime.datetime:
        return {"type": "string", "format": "date-time"}
    if py_type is datetime.date:
        return {"type": "string", "format": "date"}

    return {"type": OPENAPI_TYPE_MAP.get(py_type, "string")}


def _generate_struct_schema(
    struct_class: Type[Struct],
    components: Dict[str, Dict[str, Any]],
    visited: Set[Type],
) -> Dict[str, Any]:
    """JSON Schema dictionary for a msgspec Struct (populates components for nested Structs)."""
    properties: Dict[str, Any] = {}
    required: List[str] = []

    annotations = getattr(struct_class, "__annotations__", {})
    for field_name in getattr(struct_class, "__struct_fields__", annotations.keys()):
        field_type = annotations.get(field_name, str)
        base_type, is_opt = TypeUtils.unwrap_optional(field_type)
        prop_schema = _schema_for_python_type(base_type, components, visited)
        if is_opt:
            prop_schema["nullable"] = True
        properties[field_name] = prop_schema
        if not is_opt:
            required.append(field_name)

    schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def build_components_for_struct(struct_class: Type[Struct]) -> Dict[str, Dict[str, Any]]:
    """Build all component schemas for `struct_class` and any nested Structs."""
    components: Dict[str, Dict[str, Any]] = {}
    visited: Set[Type] = set()
    name = struct_class.__name__
    components[name] = _generate_struct_schema(struct_class, components, visited)
    return components
