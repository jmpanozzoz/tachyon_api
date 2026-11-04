"""msgspec schemas adapted to OpenAPI 3.0 component references."""

import datetime
from typing import Any, Dict, Set, Type, get_args, get_origin

import msgspec

from ..models import Struct


def _openapi_schema(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    schema = dict(value)
    for unsupported in ("prefixItems", "propertyNames"):
        if unsupported in schema:
            raise TypeError(
                f"OpenAPI 3.0 cannot represent JSON Schema {unsupported!r}; "
                "use a supported model type or set include_in_schema=False"
            )
    if "examples" in schema:
        examples = schema.pop("examples")
        if examples:
            schema.setdefault("example", examples[0])
    if "contentEncoding" in schema:
        encoding = schema.pop("contentEncoding")
        if encoding != "base64":
            raise TypeError(f"OpenAPI 3.0 cannot represent contentEncoding {encoding!r}")
        schema["format"] = "byte"
    variants = schema.get("anyOf")
    if variants and {"type": "null"} in variants:
        variants = [item for item in variants if item != {"type": "null"}]
        schema.pop("anyOf")
        if len(variants) == 1:
            schema.update(variants[0])
        else:
            schema["anyOf"] = variants
        schema["nullable"] = True
    if "const" in schema:
        schema["enum"] = [schema.pop("const")]
    if schema.get("type") == "null":
        schema.pop("type")
        schema["nullable"] = True
    for exclusive, bound, stronger in (
        ("exclusiveMinimum", "minimum", max),
        ("exclusiveMaximum", "maximum", min),
    ):
        limit = schema.get(exclusive)
        if type(limit) in (int, float):
            existing = schema.get(bound, limit)
            schema[bound] = stronger(existing, limit)
            schema[exclusive] = schema[bound] == limit
    # Only these positions contain schemas. Property names and JSON payloads
    # under default/example/enum are user data, even when named like keywords.
    if "properties" in schema:
        schema["properties"] = {name: _openapi_schema(item) for name, item in schema["properties"].items()}
    for keyword in ("allOf", "anyOf", "oneOf"):
        if keyword in schema:
            schema[keyword] = [_openapi_schema(item) for item in schema[keyword]]
    for keyword in ("items", "additionalProperties", "not"):
        if isinstance(schema.get(keyword), dict):
            schema[keyword] = _openapi_schema(schema[keyword])
    return schema


def _schema_for_python_type(py_type: Type, components: Dict[str, Dict[str, Any]], visited: Set[Type]) -> Dict[str, Any]:
    schemas, definitions = msgspec.json.schema_components(
        (py_type,), ref_template="#/components/schemas/{name}"
    )
    components.update({name: _openapi_schema(schema) for name, schema in definitions.items()})
    schema = _openapi_schema(schemas[0])
    _datetime_formats(py_type, schema, components, set())
    return schema


def _datetime_formats(py_type: Type, schema: Dict, components: Dict, visited: Set) -> None:
    # msgspec omits date-time for unconstrained datetimes (naive values are
    # allowed). Retain the framework's existing OpenAPI format hint.
    if py_type is datetime.datetime:
        schema["format"] = "date-time"
    elif isinstance(py_type, type) and issubclass(py_type, Struct):
        if py_type in visited:
            return
        visited.add(py_type)
        component = components[schema["$ref"].rsplit("/", 1)[1]]
        for field in msgspec.structs.fields(py_type):
            field_schema = component.get("properties", {}).get(field.encode_name)
            if field_schema is not None:
                _datetime_formats(field.type, field_schema, components, visited)
    else:
        args = get_args(py_type)
        if schema.get("nullable") and len(args) == 2 and type(None) in args:
            _datetime_formats(next(arg for arg in args if arg is not type(None)), schema, components, visited)
        elif get_origin(py_type) is list and args:
            _datetime_formats(args[0], schema["items"], components, visited)


def _generate_struct_schema(struct_class: Type[Struct], components: Dict[str, Dict[str, Any]], visited: Set[Type]) -> Dict[str, Any]:
    ref = _schema_for_python_type(struct_class, components, visited)
    return components[ref["$ref"].rsplit("/", 1)[1]]


def build_components_for_struct(struct_class: Type[Struct]) -> Dict[str, Dict[str, Any]]:
    components: Dict[str, Dict[str, Any]] = {}
    _schema_for_python_type(struct_class, components, set())
    return components
