"""Parameter extraction and validation — uses pre-compiled endpoint descriptors."""

from __future__ import annotations

import typing
from typing import Dict, Any, Optional

import msgspec

from starlette.requests import Request
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

_DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB


class ParameterProcessor:
    def __init__(self, app_instance):
        self.app = app_instance

    async def process_parameters(
        self,
        compiled: CompiledEndpoint,
        request: Request,
        dependency_cache: Dict,
    ) -> tuple[Dict[str, Any], Optional[JSONResponse], Optional[BackgroundTasks]]:
        kwargs: Dict[str, Any] = {}
        _bg: Optional[BackgroundTasks] = None
        _form_data = None

        for p in compiled.params:
            kind = p.kind

            if kind == KIND_REQUEST:
                kwargs[p.name] = request

            elif kind == KIND_BG:
                if _bg is None:
                    _bg = BackgroundTasks()
                kwargs[p.name] = _bg

            elif kind == KIND_DEP_CALLABLE:
                resolved = await self.app._dependency_resolver.resolve_callable_dependency(
                    p.dependency, dependency_cache, request
                )
                kwargs[p.name] = resolved

            elif kind == KIND_DEP_CLASS:
                kwargs[p.name] = self.app._dependency_resolver.resolve_dependency(p.annotation)

            elif kind == KIND_BODY:
                err = await self._process_body(p, request, kwargs)
                if err is not None:
                    return kwargs, err, _bg

            elif kind == KIND_QUERY:
                err = self._process_query(p, request.query_params, kwargs)
                if err is not None:
                    return kwargs, err, _bg

            elif kind == KIND_HEADER:
                err = self._process_header(p, request, kwargs)
                if err is not None:
                    return kwargs, err, _bg

            elif kind == KIND_COOKIE:
                err = self._process_cookie(p, request, kwargs)
                if err is not None:
                    return kwargs, err, _bg

            elif kind == KIND_FORM:
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return kwargs, validation_error_response("Failed to parse form data"), _bg
                err = self._process_form(p, _form_data, kwargs)
                if err is not None:
                    return kwargs, err, _bg

            elif kind == KIND_FILE:
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return kwargs, validation_error_response("Failed to parse form data"), _bg
                err = self._process_file(p, _form_data, kwargs)
                if err is not None:
                    return kwargs, err, _bg

            elif kind == KIND_PATH:
                err = self._process_path(p, request.path_params, kwargs)
                if err is not None:
                    return kwargs, err, _bg

            elif kind == KIND_PATH_IMPLICIT:
                err = self._process_path(p, request.path_params, kwargs)
                if err is not None:
                    return kwargs, err, _bg

        return kwargs, None, _bg

    async def _process_body(
        self, p: ParamDescriptor, request: Request, kwargs: Dict
    ) -> Optional[JSONResponse]:
        max_body_size = getattr(self.app, "max_body_size", _DEFAULT_MAX_BODY_SIZE)
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > max_body_size:
                    return validation_error_response(
                        f"Request body too large (max {max_body_size} bytes)"
                    )
            except ValueError:
                pass

        try:
            raw_body = await request.body()
        except Exception:
            return validation_error_response("Failed to read request body")

        if len(raw_body) > max_body_size:
            return validation_error_response(
                f"Request body too large (max {max_body_size} bytes)"
            )

        # Use pre-compiled decoder (cached at registration time)
        decoder = p.decoder
        if decoder is None:
            return validation_error_response("Body type must be a Struct subclass")

        try:
            kwargs[p.name] = decoder.decode(raw_body)
            return None
        except msgspec.DecodeError as e:
            return validation_error_response(f"Invalid JSON body: {e}")
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
            return validation_error_response(str(e), errors=field_errors)

    def _process_query(
        self, p: ParamDescriptor, query_params, kwargs: Dict
    ) -> Optional[JSONResponse]:
        name = p.name

        if p.is_list:
            # getlist is always available on Starlette QueryParams
            raw_values = query_params.getlist(name)
            if not raw_values and name in query_params:
                raw_values = [query_params[name]]
            # Flatten comma-separated values
            values: list = []
            for v in raw_values:
                if isinstance(v, str) and "," in v:
                    values.extend(v.split(","))
                else:
                    values.append(v)
            if not values:
                if p.default is not ...:
                    kwargs[name] = p.default
                    return None
                return validation_error_response(f"Missing required query parameter: {name}")
            converted = TypeConverter.convert_list_values(values, p.item_type, name, is_path_param=False)
            if isinstance(converted, JSONResponse):
                return converted
            kwargs[name] = converted
            return None

        if name in query_params:
            converted = TypeConverter.convert_value(
                query_params[name], p.base_type, name, is_path_param=False
            )
            if isinstance(converted, JSONResponse):
                return converted
            kwargs[name] = converted
        elif p.default is not ...:
            kwargs[name] = p.default
        else:
            return validation_error_response(f"Missing required query parameter: {name}")
        return None

    def _process_header(
        self, p: ParamDescriptor, request: Request, kwargs: Dict
    ) -> Optional[JSONResponse]:
        value = request.headers.get(p.effective_name)
        if value is not None:
            kwargs[p.name] = value
        elif p.default is not ...:
            kwargs[p.name] = p.default
        else:
            return validation_error_response(f"Missing required header: {p.effective_name}")
        return None

    def _process_cookie(
        self, p: ParamDescriptor, request: Request, kwargs: Dict
    ) -> Optional[JSONResponse]:
        value = request.cookies.get(p.effective_name)
        if value is not None:
            kwargs[p.name] = value
        elif p.default is not ...:
            kwargs[p.name] = p.default
        else:
            return validation_error_response(f"Missing required cookie: {p.effective_name}")
        return None

    def _process_form(
        self, p: ParamDescriptor, form_data, kwargs: Dict
    ) -> Optional[JSONResponse]:
        name = p.effective_name
        if name in form_data:
            kwargs[p.name] = form_data[name]
        elif p.default is not ...:
            kwargs[p.name] = p.default
        else:
            return validation_error_response(f"Missing required form field: {name}")
        return None

    def _process_file(
        self, p: ParamDescriptor, form_data, kwargs: Dict
    ) -> Optional[JSONResponse]:
        name = p.effective_name
        if name in form_data:
            uploaded = form_data[name]
            if hasattr(uploaded, "filename"):
                kwargs[p.name] = uploaded
            elif p.default is not ...:
                kwargs[p.name] = p.default
            else:
                return validation_error_response(f"Invalid file upload for: {name}")
        elif p.default is not ...:
            kwargs[p.name] = p.default
        else:
            return validation_error_response(f"Missing required file: {name}")
        return None

    def _process_path(
        self, p: ParamDescriptor, path_params: Dict, kwargs: Dict
    ) -> Optional[JSONResponse]:
        name = p.name
        if name not in path_params:
            if p.kind == KIND_PATH:
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            return None

        value_str = path_params[name]

        if p.is_list:
            parts = value_str.split(",") if value_str else []
            converted = TypeConverter.convert_list_values(
                parts, p.item_type, name, is_path_param=True
            )
            if isinstance(converted, JSONResponse):
                return converted
            kwargs[name] = converted
        else:
            converted = TypeConverter.convert_value(
                value_str, p.annotation, name, is_path_param=True
            )
            if isinstance(converted, JSONResponse):
                return converted
            kwargs[name] = converted

        return None
