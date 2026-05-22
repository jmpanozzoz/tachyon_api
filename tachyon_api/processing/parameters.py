"""Parameter extraction and validation — uses pre-compiled endpoint descriptors."""

from __future__ import annotations

import typing
from typing import Any, Optional, Tuple

import msgspec

from starlette.responses import JSONResponse

from ..models import Struct
from ..responses import validation_error_response
from ..utils import TypeConverter, TypeUtils
from ..background import BackgroundTasks
from .compiler import (
    CompiledEndpoint,
    ParamDescriptor,
    KIND_REQUEST, KIND_BG, KIND_BODY, KIND_QUERY,
    KIND_HEADER, KIND_COOKIE, KIND_FORM, KIND_FILE,
    KIND_PATH, KIND_PATH_IMPLICIT, KIND_DEP_CALLABLE, KIND_DEP_CLASS,
)
from .scope import TachyonScope

_DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB


class ParameterProcessor:
    def __init__(self, app_instance):
        self.app = app_instance

    async def process_parameters(
        self,
        compiled: CompiledEndpoint,
        request: TachyonScope,
        dependency_cache,
    ) -> Tuple[list, Optional[JSONResponse], Optional[BackgroundTasks]]:
        # Pre-allocate list of exact size — positional args for func(*args) call.
        # Avoids dict allocation + dict-write overhead on every request.
        args: list = [None] * compiled.param_count
        _bg: Optional[BackgroundTasks] = None
        _form_data = None

        for i, p in enumerate(compiled.params):
            kind = p.kind

            if kind == KIND_REQUEST:
                # User declared `request: Request` — materialise the full Starlette object
                args[i] = request.as_request()

            elif kind == KIND_BG:
                if _bg is None:
                    _bg = BackgroundTasks()
                args[i] = _bg

            elif kind == KIND_DEP_CALLABLE:
                args[i] = await self.app._dependency_resolver.resolve_callable_dependency(
                    p.dependency, dependency_cache, request
                )

            elif kind == KIND_DEP_CLASS:
                args[i] = self.app._dependency_resolver.resolve_dependency(p.annotation)

            elif kind == KIND_BODY:
                val, err = await self._process_body(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == KIND_QUERY:
                val, err = self._process_query(p, request.query_params)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == KIND_HEADER:
                val, err = self._process_header(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == KIND_COOKIE:
                val, err = self._process_cookie(p, request)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == KIND_FORM:
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), _bg
                val, err = self._process_form(p, _form_data)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == KIND_FILE:
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return args, validation_error_response("Failed to parse form data"), _bg
                val, err = self._process_file(p, _form_data)
                if err is not None:
                    return args, err, _bg
                args[i] = val

            elif kind == KIND_PATH or kind == KIND_PATH_IMPLICIT:
                val, err = self._process_path(p, request.path_params)
                if err is not None:
                    return args, err, _bg
                args[i] = val

        return args, None, _bg

    async def _process_body(
        self, p: ParamDescriptor, request: TachyonScope
    ) -> Tuple[Any, Optional[JSONResponse]]:
        max_body_size = getattr(self.app, "max_body_size", _DEFAULT_MAX_BODY_SIZE)
        cl = request.headers.get("content-length")
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

        decoder = p.decoder
        if decoder is None:
            return None, validation_error_response("Body type must be a Struct subclass")

        try:
            return decoder.decode(raw_body), None
        except msgspec.DecodeError as e:
            return None, validation_error_response(f"Invalid JSON body: {e}")
        except msgspec.ValidationError as e:
            field_errors = None
            try:
                path = getattr(e, "path", None)
                if path:
                    for seg in reversed(path):
                        if isinstance(seg, str):
                            field_errors = {seg: [str(e)]}
                            break
            except Exception:
                pass
            return None, validation_error_response(str(e), errors=field_errors)

    def _process_query(
        self, p: ParamDescriptor, query_params
    ) -> Tuple[Any, Optional[JSONResponse]]:
        name = p.name

        if p.is_list:
            raw_values = query_params.getlist(name)
            if not raw_values and name in query_params:
                raw_values = [query_params[name]]
            values: list = []
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
            converted = TypeConverter.convert_value_bare(
                query_params[name], p.base_type, name, is_path_param=False
            )
            if isinstance(converted, JSONResponse):
                return None, converted
            return converted, None
        elif p.default is not ...:
            return p.default, None
        return None, validation_error_response(f"Missing required query parameter: {name}")

    def _process_header(
        self, p: ParamDescriptor, request: TachyonScope
    ) -> Tuple[Any, Optional[JSONResponse]]:
        value = request.headers.get(p.effective_name)
        if value is not None:
            return value, None
        elif p.default is not ...:
            return p.default, None
        return None, validation_error_response(f"Missing required header: {p.effective_name}")

    def _process_cookie(
        self, p: ParamDescriptor, request: TachyonScope
    ) -> Tuple[Any, Optional[JSONResponse]]:
        value = request.cookies.get(p.effective_name)
        if value is not None:
            return value, None
        elif p.default is not ...:
            return p.default, None
        return None, validation_error_response(f"Missing required cookie: {p.effective_name}")

    def _process_form(
        self, p: ParamDescriptor, form_data
    ) -> Tuple[Any, Optional[JSONResponse]]:
        name = p.effective_name
        if name in form_data:
            return form_data[name], None
        elif p.default is not ...:
            return p.default, None
        return None, validation_error_response(f"Missing required form field: {name}")

    def _process_file(
        self, p: ParamDescriptor, form_data
    ) -> Tuple[Any, Optional[JSONResponse]]:
        name = p.effective_name
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

    def _process_path(
        self, p: ParamDescriptor, path_params
    ) -> Tuple[Any, Optional[JSONResponse]]:
        name = p.name
        if name not in path_params:
            if p.kind == KIND_PATH:
                return None, JSONResponse({"detail": "Not Found"}, status_code=404)
            return None, None

        value_str = path_params[name]
        if "\x00" in value_str:
            return None, validation_error_response(f"Invalid path parameter: {name}")

        if p.is_list:
            parts = value_str.split(",") if value_str else []
            converted = TypeConverter.convert_list_values_bare(
                parts, p.item_type, p.item_is_optional, name, is_path_param=True
            )
            if isinstance(converted, JSONResponse):
                return None, converted
            return converted, None

        converted = TypeConverter.convert_value_bare(
            value_str, p.base_type, name, is_path_param=True
        )
        if isinstance(converted, JSONResponse):
            return None, converted
        return converted, None
