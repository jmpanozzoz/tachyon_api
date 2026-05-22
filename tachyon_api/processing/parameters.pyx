# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-compiled parameter processor.

F7: process_parameters returns a list (positional args) instead of a dict.
    - Pre-allocated [None] * param_count avoids dict creation overhead.
    - list[i] = value is a C array write vs dict __setitem__.
    - call_endpoint uses func(*args) instead of func(**kwargs).
    - _process_* helpers return (value, error) tuples — no dict writes.
"""

import cython
import msgspec
import typing

from libc.stdlib cimport strtol, strtod
from cpython.unicode cimport PyUnicode_AsUTF8AndSize as _utf8ptr

from starlette.responses import JSONResponse

from ..responses import validation_error_response
from ..utils import TypeConverter, TypeUtils
from ..background import BackgroundTasks
from .compiler import (
    KIND_REQUEST, KIND_BG, KIND_BODY, KIND_QUERY,
    KIND_HEADER, KIND_COOKIE, KIND_FORM, KIND_FILE,
    KIND_PATH, KIND_PATH_IMPLICIT, KIND_DEP_CALLABLE, KIND_DEP_CLASS,
)
from .scope import TachyonScope


# ── F11: C stdlib fast converters ────────────────────────────────────────────
# Replaces TypeConverter.convert_value_bare() Python boundary crossing for the
# two most common param types.  Called as cdef — zero Python dispatch overhead.

cdef object _fast_int(str s, bint is_path_param):
    """strtol-based int parse — C stdlib, zero Python function-call overhead."""
    cdef Py_ssize_t n
    cdef char* p = <char*>_utf8ptr(s, &n)
    cdef char* ep = NULL
    cdef long v

    if n == 0 or p == NULL:
        if is_path_param:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return validation_error_response("Invalid value for integer conversion")

    v = strtol(p, &ep, 10)
    if ep == NULL or ep - p != n:
        if is_path_param:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return validation_error_response("Invalid value for integer conversion")
    return v


cdef object _fast_float(str s, bint is_path_param):
    """strtod-based float parse — C stdlib, zero Python function-call overhead."""
    cdef Py_ssize_t n
    cdef char* p = <char*>_utf8ptr(s, &n)
    cdef char* ep = NULL
    cdef double v

    if n == 0 or p == NULL:
        if is_path_param:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return validation_error_response("Invalid value for float conversion")

    v = strtod(p, &ep)
    if ep == NULL or ep - p != n:
        if is_path_param:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return validation_error_response("Invalid value for float conversion")
    return v

# C-level integer constants — avoids Python object lookup on each comparison
cdef int _KIND_REQUEST       = KIND_REQUEST
cdef int _KIND_BG            = KIND_BG
cdef int _KIND_BODY          = KIND_BODY
cdef int _KIND_QUERY         = KIND_QUERY
cdef int _KIND_HEADER        = KIND_HEADER
cdef int _KIND_COOKIE        = KIND_COOKIE
cdef int _KIND_FORM          = KIND_FORM
cdef int _KIND_FILE          = KIND_FILE
cdef int _KIND_PATH          = KIND_PATH
cdef int _KIND_PATH_IMPLICIT = KIND_PATH_IMPLICIT
cdef int _KIND_DEP_CALLABLE  = KIND_DEP_CALLABLE
cdef int _KIND_DEP_CLASS     = KIND_DEP_CLASS

cdef int _DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024


cdef class ParameterProcessor:
    """Parameter extractor — returns positional args list, zero dict overhead."""

    cdef object app

    def __init__(self, app_instance):
        self.app = app_instance

    async def process_parameters(self, compiled, request, dependency_cache):
        # Pre-allocate exact-size list — C array under the hood in CPython.
        # Index write (args[i] = v) is ~2× faster than dict write (kwargs[k] = v).
        cdef list args = [None] * compiled.param_count
        cdef object _bg = None
        cdef object _form_data = None
        cdef int kind
        cdef int i = 0
        cdef object p
        cdef object val
        cdef object err

        for p in compiled.params:
            kind = p.kind  # int field from cdef class — direct C read

            if kind == _KIND_REQUEST:
                args[i] = request.as_request()

            elif kind == _KIND_BG:
                if _bg is None:
                    _bg = BackgroundTasks()
                args[i] = _bg

            elif kind == _KIND_DEP_CALLABLE:
                args[i] = await self.app._dependency_resolver.resolve_callable_dependency(
                    p.dependency, dependency_cache, request
                )

            elif kind == _KIND_DEP_CLASS:
                args[i] = self.app._dependency_resolver.resolve_dependency(p.annotation)

            elif kind == _KIND_BODY:
                val, err = await self._process_body(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_QUERY:
                val, err = self._process_query(p, request.query_params)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_HEADER:
                val, err = self._process_header(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_COOKIE:
                val, err = self._process_cookie(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_FORM:
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), _bg
                val, err = self._process_form(p, _form_data)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_FILE:
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), _bg
                val, err = self._process_file(p, _form_data)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_PATH or kind == _KIND_PATH_IMPLICIT:
                val, err = self._process_path(p, request.path_params)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            i += 1

        return args, None, _bg

    # ── cdef helpers — return (value, error), compiled as C functions ─────────

    async def _process_body(self, p, request):
        cdef int max_body_size = getattr(self.app, "max_body_size", _DEFAULT_MAX_BODY_SIZE)
        cdef object cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > max_body_size:
                    return None, validation_error_response(
                        f"Request body too large (max {max_body_size} bytes)"
                    )
            except ValueError:
                pass
        try:
            raw_body = await request.body()
        except Exception:
            return None, validation_error_response("Failed to read request body")
        if len(raw_body) > max_body_size:
            return None, validation_error_response(
                f"Request body too large (max {max_body_size} bytes)"
            )
        cdef object decoder = p.decoder
        if decoder is None:
            return None, validation_error_response("Body type must be a Struct subclass")
        try:
            return decoder.decode(raw_body), None
        except msgspec.DecodeError as e:
            return None, validation_error_response(f"Invalid JSON body: {e}")
        except msgspec.ValidationError as e:
            field_errors = None
            try:
                path_attr = getattr(e, "path", None)
                if path_attr:
                    for seg in reversed(path_attr):
                        if isinstance(seg, str):
                            field_errors = {seg: [str(e)]}
                            break
            except Exception:
                pass
            return None, validation_error_response(str(e), errors=field_errors)

    @cython.cfunc
    def _process_query(self, p, query_params):
        cdef str name = p.name
        cdef bint is_list = p.is_list
        cdef object base_type
        cdef str raw_val

        if is_list:
            raw_values = query_params.getlist(name)
            if not raw_values and name in query_params:
                raw_values = [query_params[name]]
            values = []
            for v in raw_values:
                if isinstance(v, str) and "," in v:
                    values.extend(v.split(","))
                else:
                    values.append(v)
            if not values:
                if p.default is not ...:
                    return p.default, None
                return None, validation_error_response(f"Missing required query parameter: {name}")
            converted = TypeConverter.convert_list_values_bare(
                values, p.item_type, p.item_is_optional, name, is_path_param=False
            )
            if isinstance(converted, JSONResponse):
                return None, converted
            return converted, None

        if name in query_params:
            base_type = p.base_type
            raw_val = query_params[name]
            # F11: fast path for the two most common scalar types
            if base_type is int:
                converted = _fast_int(raw_val, False)
            elif base_type is float:
                converted = _fast_float(raw_val, False)
            else:
                converted = TypeConverter.convert_value_bare(
                    raw_val, base_type, name, is_path_param=False
                )
            if isinstance(converted, JSONResponse):
                return None, converted
            return converted, None
        elif p.default is not ...:
            return p.default, None
        return None, validation_error_response(f"Missing required query parameter: {name}")

    @cython.cfunc
    def _process_header(self, p, request):
        cdef object value = request.headers.get(p.effective_name)
        if value is not None:
            return value, None
        elif p.default is not ...:
            return p.default, None
        return None, validation_error_response(f"Missing required header: {p.effective_name}")

    @cython.cfunc
    def _process_cookie(self, p, request):
        cdef object value = request.cookies.get(p.effective_name)
        if value is not None:
            return value, None
        elif p.default is not ...:
            return p.default, None
        return None, validation_error_response(f"Missing required cookie: {p.effective_name}")

    @cython.cfunc
    def _process_form(self, p, form_data):
        cdef str name = p.effective_name
        if name in form_data:
            return form_data[name], None
        elif p.default is not ...:
            return p.default, None
        return None, validation_error_response(f"Missing required form field: {name}")

    @cython.cfunc
    def _process_file(self, p, form_data):
        cdef str name = p.effective_name
        if name in form_data:
            uploaded = form_data[name]
            if hasattr(uploaded, "filename"):
                return uploaded, None
            elif p.default is not ...:
                return p.default, None
            return None, validation_error_response(f"Invalid file upload for: {name}")
        elif p.default is not ...:
            return p.default, None
        return None, validation_error_response(f"Missing required file: {name}")

    @cython.cfunc
    def _process_path(self, p, path_params):
        cdef str name = p.name
        cdef str value_str
        cdef bint is_list = p.is_list
        cdef object pt

        if name not in path_params:
            if p.kind == _KIND_PATH:
                return None, JSONResponse({"detail": "Not Found"}, status_code=404)
            return None, None

        value_str = path_params[name]

        if is_list:
            parts = value_str.split(",") if value_str else []
            converted = TypeConverter.convert_list_values_bare(
                parts, p.item_type, p.item_is_optional, name, is_path_param=True
            )
            if isinstance(converted, JSONResponse):
                return None, converted
            return converted, None

        # F11: fast path for the two most common path param types
        pt = p.base_type
        if pt is int:
            converted = _fast_int(value_str, True)
        elif pt is float:
            converted = _fast_float(value_str, True)
        else:
            converted = TypeConverter.convert_value_bare(
                value_str, pt, name, is_path_param=True
            )
        if isinstance(converted, JSONResponse):
            return None, converted
        return converted, None
