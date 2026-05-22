# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled scalar query extractor.

Includes the F11 fast-int / fast-float path: when the descriptor's base_type
is int or float, conversion goes through C stdlib's strtol/strtod instead of
TypeConverter.convert_value_bare (which crosses the Python boundary).  These
two types cover the vast majority of typed query params in practice
(pagination offsets, limits, IDs, prices) so the fast-path is worth the
~15 extra lines.
"""

from libc.stdlib cimport strtol, strtod
from cpython.unicode cimport PyUnicode_AsUTF8AndSize as _utf8ptr

from starlette.responses import JSONResponse

from ...responses import validation_error_response
from ...utils import TypeConverter
from ._missing import missing


cdef object _fast_int(str s):
    """strtol-based int parse — C stdlib; returns int or 422 JSONResponse on failure."""
    cdef Py_ssize_t n
    cdef char* p = <char*>_utf8ptr(s, &n)
    cdef char* ep = NULL
    cdef long v

    if n == 0 or p == NULL:
        return validation_error_response("Invalid value for integer conversion")

    v = strtol(p, &ep, 10)
    if ep == NULL or ep - p != n:
        return validation_error_response("Invalid value for integer conversion")
    return v


cdef object _fast_float(str s):
    """strtod-based float parse — C stdlib; returns float or 422 JSONResponse on failure."""
    cdef Py_ssize_t n
    cdef char* p = <char*>_utf8ptr(s, &n)
    cdef char* ep = NULL
    cdef double v

    if n == 0 or p == NULL:
        return validation_error_response("Invalid value for float conversion")

    v = strtod(p, &ep)
    if ep == NULL or ep - p != n:
        return validation_error_response("Invalid value for float conversion")
    return v


cdef class QueryExtractor:
    """Extracts a single scalar query parameter and converts to its declared type."""

    cpdef extract(self, object descriptor, object query_params):
        cdef str name = descriptor.name
        cdef str raw_val
        cdef object base_type

        if name not in query_params:
            return missing(descriptor, "query parameter", name)

        base_type = descriptor.base_type
        raw_val = query_params[name]

        # F11 fast paths — preserved from the pre-v1.2.9 parameters.pyx
        if base_type is int:
            converted = _fast_int(raw_val)
        elif base_type is float:
            converted = _fast_float(raw_val)
        else:
            converted = TypeConverter.convert_value_bare(
                raw_val, base_type, name, is_path_param=False
            )

        if isinstance(converted, JSONResponse):
            return (None, converted)
        return (converted, None)
