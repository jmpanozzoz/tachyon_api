# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled path-parameter extractor.

Rejects null bytes (v1.2.0 path-traversal hardening), then type-converts the
remaining string.  Includes the F11 fast-int / fast-float path: when the
descriptor's base_type is int or float, conversion goes through C stdlib's
strtol/strtod instead of TypeConverter.

For path params, conversion failure returns a 404 (not 422) — matches the
existing routing semantics where a wrong-typed path "doesn't exist".
"""

from libc.stdlib cimport strtol, strtod
from cpython.unicode cimport PyUnicode_AsUTF8AndSize as _utf8ptr

from starlette.responses import JSONResponse

from ..compiler import KIND_PATH
from ...responses import validation_error_response
from ...utils import TypeConverter


cdef object _fast_int_path(str s):
    """strtol-based int parse — returns int or 404 JSONResponse on failure."""
    cdef Py_ssize_t n
    cdef char* p = <char*>_utf8ptr(s, &n)
    cdef char* ep = NULL
    cdef long v

    if n == 0 or p == NULL:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    v = strtol(p, &ep, 10)
    if ep == NULL or ep - p != n:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return v


cdef object _fast_float_path(str s):
    """strtod-based float parse — returns float or 404 JSONResponse on failure."""
    cdef Py_ssize_t n
    cdef char* p = <char*>_utf8ptr(s, &n)
    cdef char* ep = NULL
    cdef double v

    if n == 0 or p == NULL:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    v = strtod(p, &ep)
    if ep == NULL or ep - p != n:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return v


cdef class PathExtractor:
    """Extracts a path parameter, with null-byte rejection and type conversion."""

    def extract(self, descriptor, path_params):
        cdef str name = descriptor.name
        cdef str value_str
        cdef object base_type

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
            base_type = descriptor.base_type
            # F11 fast paths — preserved from the pre-v1.2.9 parameters.pyx
            if base_type is int:
                converted = _fast_int_path(value_str)
            elif base_type is float:
                converted = _fast_float_path(value_str)
            else:
                converted = TypeConverter.convert_value_bare(
                    value_str, base_type, name, is_path_param=True
                )

        if isinstance(converted, JSONResponse):
            return (None, converted)
        return (converted, None)
