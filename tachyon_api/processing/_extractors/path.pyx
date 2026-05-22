# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled path-parameter extractor.

Rejects null bytes (v1.2.0 path-traversal hardening) and type-converts the
remaining string via TypeConverter.
"""

from starlette.responses import JSONResponse

from ..compiler import KIND_PATH
from ...responses import validation_error_response
from ...utils import TypeConverter
from ._base import ExtractorResult


cdef class PathExtractor:
    """Extracts a path parameter, with null-byte rejection and type conversion."""

    def extract(self, descriptor, path_params):
        cdef str name = descriptor.name
        cdef str value_str

        if name not in path_params:
            if descriptor.kind == KIND_PATH:
                return ExtractorResult(
                    None, JSONResponse({"detail": "Not Found"}, status_code=404)
                )
            return ExtractorResult(None, None)

        value_str = path_params[name]
        if "\x00" in value_str:
            return ExtractorResult(
                None, validation_error_response(f"Invalid path parameter: {name}")
            )

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
            return ExtractorResult(None, converted)
        return ExtractorResult(converted, None)
