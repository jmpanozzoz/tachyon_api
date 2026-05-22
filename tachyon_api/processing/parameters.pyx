# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-compiled parameter processor — Phase 4b.2 of v1.2.9.

Orchestrator that delegates to the cdef-class extractors compiled in Phase 4a:
  HeaderExtractor · CookieExtractor · QueryExtractor (scalar) · PathExtractor.

Extractors still inlined here (Phase 4c targets):
  _process_body / _process_form / _process_file / _process_query (list path).

F11 fast-int / fast-float has moved into `query.pyx` and `path.pyx`
(Phase 4b.1).  This file no longer carries the inline strtol/strtod helpers.
"""

import cython
import msgspec
import typing

from starlette.responses import JSONResponse

from ..responses import validation_error_response
from ..utils import TypeConverter, TypeUtils
from ..background import BackgroundTasks
from ._extractors.header import HeaderExtractor
from ._extractors.cookie import CookieExtractor
from ._extractors.query import QueryExtractor
from ._extractors.path import PathExtractor
from .compiler import (
    KIND_REQUEST, KIND_BG, KIND_BODY, KIND_QUERY,
    KIND_HEADER, KIND_COOKIE, KIND_FORM, KIND_FILE,
    KIND_PATH, KIND_PATH_IMPLICIT, KIND_DEP_CALLABLE, KIND_DEP_CLASS,
)
from .scope import TachyonScope


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

cdef int _DEFAULT_MAX_BODY_SIZE = 2 * 1024 * 1024  # 2 MB — matches parameters.py (v1.2.0 audit)


cdef class ParameterProcessor:
    """Parameter extractor — orchestrator that delegates to cdef extractors."""

    cdef object app
    cdef object _header_extractor
    cdef object _cookie_extractor
    cdef object _query_extractor
    cdef object _path_extractor

    def __init__(self, app_instance):
        self.app = app_instance
        self._header_extractor = HeaderExtractor()
        self._cookie_extractor = CookieExtractor()
        self._query_extractor = QueryExtractor()
        self._path_extractor = PathExtractor()

    async def process_parameters(self, compiled, request, dependency_cache):
        # Pre-allocate exact-size list — C array under the hood in CPython.
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
                # Phase 4c — still inline
                val, err = await self._process_body(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_QUERY:
                # Delegate scalar to QueryExtractor (cdef class with F11).
                # List path stays inline until Phase 4c brings query_list.pyx in.
                if p.is_list:
                    val, err = self._process_query_list(p, request.query_params)
                else:
                    val, err = self._query_extractor.extract(p, request.query_params)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_HEADER:
                val, err = self._header_extractor.extract(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_COOKIE:
                val, err = self._cookie_extractor.extract(p, request)
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
                # Delegate to PathExtractor — handles scalar (F11 fast int/float)
                # and list (TypeConverter), plus the null-byte security check.
                val, err = self._path_extractor.extract(p, request.path_params)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            i += 1

        return args, None, _bg

    # ── still-inline helpers (Phase 4c migrates these out) ────────────────────

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
    def _process_query_list(self, p, query_params):
        cdef str name = p.name
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
