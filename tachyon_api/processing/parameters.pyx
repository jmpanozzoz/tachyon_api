# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython-compiled parameter processor — Phase 4c of v1.2.9.

Orchestrator that delegates to the eight cdef-class extractors:
  HeaderExtractor · CookieExtractor · QueryExtractor (scalar) · PathExtractor
  BodyExtractor · FormExtractor · FileExtractor · QueryListExtractor.

No more inline `_process_*` methods.  This file is now purely a dispatch loop:
read `kind`, call the matching extractor, unpack `(value, error)`.

F11 fast-int / fast-float live in `query.pyx` and `path.pyx`.
Body size limit is captured in BodyExtractor at construction time.
"""

import cython

from starlette.responses import JSONResponse

from ..responses import validation_error_response
from ..background import BackgroundTasks

# Python imports for instantiation
from ._extractors.header import HeaderExtractor as _HeaderExtractor_py
from ._extractors.cookie import CookieExtractor as _CookieExtractor_py
from ._extractors.query import QueryExtractor as _QueryExtractor_py
from ._extractors.path import PathExtractor as _PathExtractor_py
from ._extractors.body import BodyExtractor as _BodyExtractor_py
from ._extractors.form import FormExtractor as _FormExtractor_py
from ._extractors.file import FileExtractor as _FileExtractor_py
from ._extractors.query_list import QueryListExtractor as _QueryListExtractor_py

# C-level cimport — direct cdef class slot dispatch (Phase 4b.3 + 4c).
from ._extractors.header cimport HeaderExtractor
from ._extractors.cookie cimport CookieExtractor
from ._extractors.query cimport QueryExtractor
from ._extractors.path cimport PathExtractor
from ._extractors.body cimport BodyExtractor
from ._extractors.form cimport FormExtractor
from ._extractors.file cimport FileExtractor
from ._extractors.query_list cimport QueryListExtractor

from .compiler import (
    KIND_REQUEST, KIND_BG, KIND_BODY, KIND_QUERY,
    KIND_HEADER, KIND_COOKIE, KIND_FORM, KIND_FILE,
    KIND_PATH, KIND_PATH_IMPLICIT, KIND_DEP_CALLABLE, KIND_DEP_CLASS,
)


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
    """Parameter orchestrator — delegates to typed cdef-class extractors.

    All eight extractors are stored as typed cdef-class references.  Combined
    with `cpdef extract(...)` declared in each `.pxd` (or `async def` for the
    body extractor), Cython emits direct C slot dispatch on every call.
    """

    cdef object app
    cdef HeaderExtractor _header
    cdef CookieExtractor _cookie
    cdef QueryExtractor _query
    cdef PathExtractor _path
    cdef BodyExtractor _body
    cdef FormExtractor _form
    cdef FileExtractor _file
    cdef QueryListExtractor _query_list

    def __init__(self, app_instance):
        cdef int max_body_size = getattr(app_instance, "max_body_size", _DEFAULT_MAX_BODY_SIZE)
        self.app = app_instance
        # Use the Python-imported aliases for instantiation (cimport names
        # refer only to the C-level type, not callable as constructor here).
        self._header = _HeaderExtractor_py()
        self._cookie = _CookieExtractor_py()
        self._query = _QueryExtractor_py()
        self._path = _PathExtractor_py()
        self._body = _BodyExtractor_py(max_body_size)
        self._form = _FormExtractor_py()
        self._file = _FileExtractor_py()
        self._query_list = _QueryListExtractor_py()

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
                val, err = await self._body.extract(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_QUERY:
                if p.is_list:
                    val, err = self._query_list.extract(p, request.query_params)
                else:
                    val, err = self._query.extract(p, request.query_params)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_HEADER:
                val, err = self._header.extract(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_COOKIE:
                val, err = self._cookie.extract(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_FORM:
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), _bg
                val, err = self._form.extract(p, _form_data)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_FILE:
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), _bg
                val, err = self._file.extract(p, _form_data)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == _KIND_PATH or kind == _KIND_PATH_IMPLICIT:
                val, err = self._path.extract(p, request.path_params)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            i += 1

        return args, None, _bg
