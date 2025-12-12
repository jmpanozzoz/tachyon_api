"""
Parameter processing for Tachyon applications.

Handles extraction and validation of:
- Path parameters
- Query parameters  
- Body parameters
- Header parameters
- Cookie parameters
- Form parameters
- File uploads
"""

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
    """
    Processes and extracts parameters from HTTP requests.
    
    This class encapsulates all the complex logic for:
    - Detecting parameter types
    - Extracting values from request
    - Type conversion and validation
    - Handling optional/required parameters
    """
    
    def __init__(self, app_instance):
        """
        Initialize parameter processor.
        
        Args:
            app_instance: The Tachyon app instance (for dependency resolution)
        """
        self.app = app_instance
    
    async def process_parameters(
        self,
        endpoint_func,
        request: Request,
        dependency_cache: Dict,
    ) -> tuple[Dict[str, Any], Optional[JSONResponse], Optional[Any]]:
        """
        Process all parameters for an endpoint function.
        
        Args:
            endpoint_func: The endpoint function to analyze
            request: The incoming HTTP request
            dependency_cache: Cache for callable dependencies
        
        Returns:
            Tuple of (kwargs_to_inject, error_response, background_tasks)
            - kwargs_to_inject: Dictionary of parameter name -> value
            - error_response: JSONResponse if validation error occurred, None otherwise
            - background_tasks: BackgroundTasks instance if requested, None otherwise
        """
        kwargs_to_inject = {}
        sig = inspect.signature(endpoint_func)
        query_params = request.query_params
        path_params = request.path_params
        _raw_body = None
        _form_data = None  # Lazy-loaded form data for Form/File params
        _background_tasks = None
        
        # Process each parameter in the endpoint function signature
        for param in sig.parameters.values():
            # Check for Request object injection
            if param.annotation is Request:
                kwargs_to_inject[param.name] = request
                continue
            
            # Check for BackgroundTasks injection
            if param.annotation is BackgroundTasks:
                if _background_tasks is None:
                    _background_tasks = BackgroundTasks()
                kwargs_to_inject[param.name] = _background_tasks
                continue
            
            # Determine if this parameter is a dependency
            is_explicit_dependency = isinstance(param.default, Depends)
            is_implicit_dependency = (
                param.default is inspect.Parameter.empty
                and param.annotation in _registry
            )
            
            # Process dependencies (explicit and implicit)
            if is_explicit_dependency or is_implicit_dependency:
                if (
                    is_explicit_dependency
                    and param.default.dependency is not None
                ):
                    # Depends(callable) - call the factory function
                    resolved = await self.app._resolve_callable_dependency(
                        param.default.dependency, dependency_cache, request
                    )
                    kwargs_to_inject[param.name] = resolved
                else:
                    # Depends() or implicit - resolve by type annotation
                    target_class = param.annotation
                    kwargs_to_inject[param.name] = self.app._resolve_dependency(
                        target_class
                    )
            
            # Process Body parameters (JSON request body)
            elif isinstance(param.default, Body):
                result = await self._process_body_param(
                    param, request, kwargs_to_inject
                )
                if result is not None:  # error response
                    return kwargs_to_inject, result, _background_tasks
                # Check if _raw_body needs updating (for subsequent body params)
                if _raw_body is None:
                    _raw_body = True  # Mark as loaded
            
            # Process Query parameters
            elif isinstance(param.default, Query):
                error_response = self._process_query_param(
                    param, query_params, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks
            
            # Process Header parameters
            elif isinstance(param.default, Header):
                error_response = self._process_header_param(
                    param, request, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks
            
            # Process Cookie parameters
            elif isinstance(param.default, Cookie):
                error_response = self._process_cookie_param(
                    param, request, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks
            
            # Process Form parameters
            elif isinstance(param.default, Form):
                if _form_data is None:
                    _form_data = await request.form()
                error_response = self._process_form_param(
                    param, _form_data, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks
            
            # Process File parameters
            elif isinstance(param.default, File):
                if _form_data is None:
                    _form_data = await request.form()
                error_response = self._process_file_param(
                    param, _form_data, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks
            
            # Process explicit Path parameters
            elif isinstance(param.default, Path):
                error_response = self._process_path_param(
                    param, path_params, kwargs_to_inject
                )
                if error_response:
                    return kwargs_to_inject, error_response, _background_tasks
            
            # Process implicit Path parameters
            elif (
                param.default is inspect.Parameter.empty
                and param.name in path_params
                and not is_explicit_dependency
                and not is_implicit_dependency
            ):
                error_response = self._process_implicit_path_param(
                    param, path_params, kwargs_to_inject
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
        """Process Body parameter."""
        model_class = param.annotation
        if not issubclass(model_class, Struct):
            raise TypeError(
                "Body type must be an instance of Tachyon_api.models.Struct"
            )
        
        decoder = msgspec.json.Decoder(model_class)
        try:
            raw_body = await request.body()
            validated_data = decoder.decode(raw_body)
            kwargs_to_inject[param.name] = validated_data
            return None
        except msgspec.ValidationError as e:
            # Attempt to build field errors map
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
        """Process Query parameter."""
        query_info = param.default
        param_name = param.name
        ann = param.annotation
        origin = typing.get_origin(ann)
        args = typing.get_args(ann)
        
        # List[T] handling
        if origin in (list, typing.List):
            item_type = args[0] if args else str
            values = []
            # collect repeated params
            if hasattr(query_params, "getlist"):
                values = query_params.getlist(param_name)
            # if not repeated, check for CSV in single value
            if not values and param_name in query_params:
                raw = query_params[param_name]
                values = raw.split(",") if "," in raw else [raw]
            # flatten CSV in any element
            flat_values = []
            for v in values:
                if isinstance(v, str) and "," in v:
                    flat_values.extend(v.split(","))
                else:
                    flat_values.append(v)
            values = flat_values
            if not values:
                if query_info.default is not ...:
                    kwargs_to_inject[param_name] = query_info.default
                    return None
                return validation_error_response(
                    f"Missing required query parameter: {param_name}"
                )
            # Unwrap Optional for item type
            base_item_type, item_is_opt = TypeUtils.unwrap_optional(item_type)
            converted_list = []
            for v in values:
                if item_is_opt and (v == "" or v.lower() == "null"):
                    converted_list.append(None)
                    continue
                converted_value = TypeConverter.convert_value(
                    v, base_item_type, param_name, is_path_param=False
                )
                if isinstance(converted_value, JSONResponse):
                    return converted_value
                converted_list.append(converted_value)
            kwargs_to_inject[param_name] = converted_list
            return None
        
        # Optional[T] handling for single value
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
        """Process Header parameter."""
        header_info = param.default
        # Use alias if provided, otherwise convert param name
        if header_info.alias:
            header_name = header_info.alias.lower()
        else:
            header_name = param.name.replace("_", "-").lower()
        
        # Get header value (case-insensitive)
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
        """Process Cookie parameter."""
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
        """Process Form parameter."""
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
        """Process File parameter."""
        file_info = param.default
        field_name = param.name
        
        if field_name in form_data:
            uploaded_file = form_data[field_name]
            # Check if it's actually a file (UploadFile)
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
    ) -> Optional[JSONResponse]:
        """Process explicit Path parameter."""
        param_name = param.name
        if param_name not in path_params:
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        
        value_str = path_params[param_name]
        ann = param.annotation
        origin = typing.get_origin(ann)
        args = typing.get_args(ann)
        
        # List[T] handling
        if origin in (list, typing.List):
            item_type = args[0] if args else str
            parts = value_str.split(",") if value_str else []
            base_item_type, item_is_opt = TypeUtils.unwrap_optional(item_type)
            converted_list = []
            for v in parts:
                if item_is_opt and (v == "" or v.lower() == "null"):
                    converted_list.append(None)
                    continue
                converted_value = TypeConverter.convert_value(
                    v, base_item_type, param_name, is_path_param=True
                )
                if isinstance(converted_value, JSONResponse):
                    return converted_value
                converted_list.append(converted_value)
            kwargs_to_inject[param_name] = converted_list
        else:
            converted_value = TypeConverter.convert_value(
                value_str, ann, param_name, is_path_param=True
            )
            if isinstance(converted_value, JSONResponse):
                return converted_value
            kwargs_to_inject[param_name] = converted_value
        
        return None
    
    def _process_implicit_path_param(
        self,
        param,
        path_params,
        kwargs_to_inject: Dict,
    ) -> Optional[JSONResponse]:
        """Process implicit Path parameter (URL path variables without Path())."""
        param_name = param.name
        value_str = path_params[param_name]
        ann = param.annotation
        origin = typing.get_origin(ann)
        args = typing.get_args(ann)
        
        # List[T] handling
        if origin in (list, typing.List):
            item_type = args[0] if args else str
            parts = value_str.split(",") if value_str else []
            base_item_type, item_is_opt = TypeUtils.unwrap_optional(item_type)
            converted_list = []
            for v in parts:
                if item_is_opt and (v == "" or v.lower() == "null"):
                    converted_list.append(None)
                    continue
                converted_value = TypeConverter.convert_value(
                    v, base_item_type, param_name, is_path_param=True
                )
                if isinstance(converted_value, JSONResponse):
                    return converted_value
                converted_list.append(converted_value)
            kwargs_to_inject[param_name] = converted_list
        else:
            converted_value = TypeConverter.convert_value(
                value_str, ann, param_name, is_path_param=True
            )
            if isinstance(converted_value, JSONResponse):
                return converted_value
            kwargs_to_inject[param_name] = converted_value
        
        return None
