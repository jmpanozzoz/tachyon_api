# HOT PATH — extracts and type-converts a path parameter.
# Rejects null bytes (path traversal hardening from v1.2.0 audit).

from starlette.responses import JSONResponse

from ..compiler import ParamDescriptor, KIND_PATH
from ...responses import validation_error_response
from ...utils import TypeConverter


class PathExtractor:
    """Extracts a path parameter, with null-byte rejection and type conversion."""

    __slots__ = ()

    def extract(self, descriptor: ParamDescriptor, path_params):
        """Returns `(value, error)` plain tuple."""
        name = descriptor.name
        if name not in path_params:
            if descriptor.kind == KIND_PATH:
                return (None, JSONResponse({"detail": "Not Found"}, status_code=404))
            return (None, None)

        value_str = path_params[name]
        if "\x00" in value_str:
            return (None, validation_error_response(f"Invalid path parameter: {name}"))

        if descriptor.is_list:
            parts = value_str.split(",") if value_str else []
            converted = TypeConverter.convert_list_values_bare(
                parts, descriptor.item_type, descriptor.item_is_optional, name, is_path_param=True
            )
        else:
            converted = TypeConverter.convert_value_bare(
                value_str, descriptor.base_type, name, is_path_param=True
            )

        if isinstance(converted, JSONResponse):
            return (None, converted)
        return (converted, None)
