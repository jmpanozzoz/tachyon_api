"""Parameter extraction and validation from HTTP requests."""

import inspect
import msgspec
import typing
from typing import Dict, Any, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from ..params import Body, Query, Path, Header, Cookie, Form, File
from ..models import Struct
from ..responses import validation_error_response
from ..utils import TypeConverter, TypeUtils
from ..background import BackgroundTasks
from ..di import Depends, _registry


class ParameterProcessor:
    def __init__(self, app_instance):
        self.app = app_instance
    
    async def process_parameters(
        self,
        endpoint_func,
        request: Request,
        dependency_cache: Dict,
    ) -> tuple[Dict[str, Any], Optional[JSONResponse], Optional[Any]]:
        kwargs_to_inject = {}
        sig = inspect.signature(endpoint_func)
        query_params = request.query_params
        path_params = request.path_params
        _form_data = None
        _background_tasks = None

        for param in sig.parameters.values():
            if param.annotation is Request:
                kwargs_to_inject[param.name] = request
                continue

            if param.annotation is BackgroundTasks:
                if _background_tasks is None:
                    _background_tasks = BackgroundTasks()
                kwargs_to_inject[param.name] = _background_tasks
                continue

            is_explicit_dependency = isinstance(param.default, Depends)
            is_implicit_dependency = (
                param.default is inspect.Parameter.empty
                and param.annotation in _registry
            )

            if is_explicit_dependency or is_implicit_dependency:
                if is_explicit_dependency and param.default.dependency is not None:
                    resolved = await self.app._dependency_resolver.resolve_callable_dependency(
                        param.default.dependency, dependency_cache, request
                    )
                    kwargs_to_inject[param.name] = resolved
                else:
                    target_class = param.annotation
                    kwargs_to_inject[param.name] = self.app._dependency_resolver.resolve_dependency(
                        target_class
                    )

            elif isinstance(param.default, Body):
                result = await self._process_body_param(
                    param, request, kwargs_to_inject
                )
                if result is not None:
                    return kwargs_to_inject, result, _background_tasks

            elif isinstance(param.default, Query):
                error_response = self._process_query_param(
                    param, query_params, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks

            elif isinstance(param.default, Header):
                error_response = self._process_header_param(
                    param, request, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks
            
            elif isinstance(param.default, Cookie):
                error_response = self._process_cookie_param(
                    param, request, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks

            elif isinstance(param.default, Form):
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return kwargs_to_inject, validation_error_response("Failed to parse form data"), _background_tasks
                error_response = self._process_form_param(
                    param, _form_data, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks

            elif isinstance(param.default, File):
                if _form_data is None:
                    try:
                        _form_data = await request.form()
                    except Exception:
                        return kwargs_to_inject, validation_error_response("Failed to parse form data"), _background_tasks
                error_response = self._process_file_param(
                    param, _form_data, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks

            elif isinstance(param.default, Path):
                error_response = self._process_path_param(
                    param, path_params, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks

            elif (
                param.default is inspect.Parameter.empty
                and param.name in path_params
                and not is_explicit_dependency
                and not is_implicit_dependency
            ):
                error_response = self._process_path_param(
                    param, path_params, kwargs_to_inject, explicit=False
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks

        return kwargs_to_inject, None, _background_tasks
    
    async def _process_body_param(
        self,
        param,
        request: Request,
        kwargs_to_inject: Dict,
    ) -> Optional[JSONResponse]:
        model_class = param.annotation
        if not issubclass(model_class, Struct):
            raise TypeError(
                "Body type must be an instance of Tachyon_api.models.Struct"
            )

        decoder = msgspec.json.Decoder(model_class)
        try:
            raw_body = await request.body()
        except Exception:
            return validation_error_response("Failed to read request body")
        try:
            validated_data = decoder.decode(raw_body)
            kwargs_to_inject[param.name] = validated_data
            return None
        except msgspec.DecodeError as e:
            return validation_error_response(f"Invalid JSON body: {e}")
        except msgspec.ValidationError as e:
            field_errors = None
            try:
                path = getattr(e, "path", None)
                if path:
                    field_name = None
                    for p in reversed(path):
                        if isinstance(p, str):
                            field_name = p
                            break
                    if field_name:
                        field_errors = {field_name: [str(e)]}
            except Exception:
                field_errors = None
            return validation_error_response(str(e), errors=field_errors)

    def _process_query_param(
        self,
        param,
        query_params,
        kwargs_to_inject: Dict,
    ) -> Optional[JSONResponse]:
        query_info = param.default
        param_name = param.name
        ann = param.annotation
        origin = typing.get_origin(ann)
        args = typing.get_args(ann)
        
        if origin in (list, typing.List):
            item_type = args[0] if args else str
            raw_values: list[str] = []
            if hasattr(query_params, "getlist"):
                raw_values = query_params.getlist(param_name)
            if not raw_values and param_name in query_params:
                raw_values = [query_params[param_name]]
            # Flatten any comma-separated values within individual entries
            values: list[str] = []
            for v in raw_values:
                if isinstance(v, str) and "," in v:
                    values.extend(v.split(","))
                else:
                    values.append(v)
            if not values:
                if query_info.default is not ...:
                    kwargs_to_inject[param_name] = query_info.default
                    return None
                return validation_error_response(
                    f"Missing required query parameter: {param_name}"
                )
            converted_list = TypeConverter.convert_list_values(
                values, item_type, param_name, is_path_param=False
            )
            if isinstance(converted_list, JSONResponse):
                return converted_list
            kwargs_to_inject[param_name] = converted_list
            return None

        base_type, _is_opt = TypeUtils.unwrap_optional(ann)

        if param_name in query_params:
            value_str = query_params[param_name]
            converted_value = TypeConverter.convert_value(
                value_str, base_type, param_name, is_path_param=False
            )
            if isinstance(converted_value, JSONResponse):
                return converted_value
            kwargs_to_inject[param_name] = converted_value
        elif query_info.default is not ...:
            kwargs_to_inject[param.name] = query_info.default
        else:
            return validation_error_response(
                f"Missing required query parameter: {param_name}"
            )
        return None
    
    def _process_header_param(
        self,
        param,
        request: Request,
        kwargs_to_inject: Dict,
    ) -> Optional[JSONResponse]:
        header_info = param.default
        header_name = header_info.alias.lower() if header_info.alias else param.name.replace("_", "-").lower()
        header_value = request.headers.get(header_name)

        if header_value is not None:
            kwargs_to_inject[param.name] = header_value
        elif header_info.default is not ...:
            kwargs_to_inject[param.name] = header_info.default
        else:
            return validation_error_response(
                f"Missing required header: {header_name}"
            )
        return None
    
    def _process_cookie_param(
        self,
        param,
        request: Request,
        kwargs_to_inject: Dict,
    ) -> Optional[JSONResponse]:
        cookie_info = param.default
        cookie_name = cookie_info.alias or param.name
        cookie_value = request.cookies.get(cookie_name)

        if cookie_value is not None:
            kwargs_to_inject[param.name] = cookie_value
        elif cookie_info.default is not ...:
            kwargs_to_inject[param.name] = cookie_info.default
        else:
            return validation_error_response(
                f"Missing required cookie: {cookie_name}"
            )
        return None
    
    def _process_form_param(
        self,
        param,
        form_data,
        kwargs_to_inject: Dict,
    ) -> Optional[JSONResponse]:
        form_info = param.default
        field_name = form_info.alias or param.name

        if field_name in form_data:
            kwargs_to_inject[param.name] = form_data[field_name]
        elif form_info.default is not ...:
            kwargs_to_inject[param.name] = form_info.default
        else:
            return validation_error_response(
                f"Missing required form field: {field_name}"
            )
        return None
    
    def _process_file_param(
        self,
        param,
        form_data,
        kwargs_to_inject: Dict,
    ) -> Optional[JSONResponse]:
        file_info = param.default
        field_name = file_info.alias or param.name

        if field_name in form_data:
            uploaded_file = form_data[field_name]
            if hasattr(uploaded_file, "filename"):
                kwargs_to_inject[param.name] = uploaded_file
            elif file_info.default is not ...:
                kwargs_to_inject[param.name] = file_info.default
            else:
                return validation_error_response(
                    f"Invalid file upload for: {field_name}"
                )
        elif file_info.default is not ...:
            kwargs_to_inject[param.name] = file_info.default
        else:
            return validation_error_response(
                f"Missing required file: {field_name}"
            )
        return None
    
    def _process_path_param(
        self,
        param,
        path_params,
        kwargs_to_inject: Dict,
        explicit: bool = True,
    ) -> Optional[JSONResponse]:
        """Process a path parameter (explicit Path() or implicit from URL)."""
        param_name = param.name
        if explicit and param_name not in path_params:
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        value_str = path_params[param_name]
        ann = param.annotation
        origin = typing.get_origin(ann)
        args = typing.get_args(ann)

        if origin in (list, typing.List):
            item_type = args[0] if args else str
            parts = value_str.split(",") if value_str else []
            converted_list = TypeConverter.convert_list_values(
                parts, item_type, param_name, is_path_param=True
            )
            if isinstance(converted_list, JSONResponse):
                return converted_list
            kwargs_to_inject[param_name] = converted_list
        else:
            converted_value = TypeConverter.convert_value(
                value_str, ann, param_name, is_path_param=True
            )
            if isinstance(converted_value, JSONResponse):
                return converted_value
            kwargs_to_inject[param_name] = converted_value

        return None

