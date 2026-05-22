# Schema generation for query / path / header / cookie parameter types.
# Handles scalars, lists, Optional, Enum, and datetime/UUID format hints.

from enum import Enum
from typing import Any, Dict, Type

from ..utils import TypeUtils
from ._format_map import _OPENAPI_FORMAT_MAP


def _scalar_schema(t: Type) -> Dict[str, Any]:
    fmt = _OPENAPI_FORMAT_MAP.get(t)
    if fmt:
        return {"type": fmt[0], "format": fmt[1]}
    if isinstance(t, type) and issubclass(t, Enum):
        members = [e.value for e in t]
        val_type = (
            "integer"
            if members and all(isinstance(v, int) for v in members)
            else "string"
        )
        return {"type": val_type, "enum": members}
    return {"type": TypeUtils.get_openapi_type(t)}


def build_param_schema(python_type: Type) -> Dict[str, Any]:
    """Build a schema for a scalar / list / optional / enum / formatted type."""
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
