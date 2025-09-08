"""
Parameter Processing System for Tachyon API

This module handles the processing and validation of different parameter types
(Body, Query, Path) for endpoint functions.
"""

import inspect
import typing
from typing import Any, Union
from starlette.responses import JSONResponse

import msgspec

from ..schemas.models import Struct
from ..schemas.parameters import Body, Query, Path
from ..schemas.responses import validation_error_response
from ..utils.type_converter import TypeConverter
from ..utils.type_utils import TypeUtils


class _NotProcessed:
    """Sentinel value to indicate that a parameter was not processed by ParameterProcessor."""

    pass


class ParameterProcessor:
    """
    Handles processing and validation of endpoint parameters.

    This class processes Body, Query, and Path parameters, performing type conversion,
    validation, and error handling for each parameter type.
    """

    @staticmethod
    async def process_body_parameter(
        param, model_class, _raw_body, request
    ) -> Union[Any, JSONResponse]:
        """
        Process a Body parameter from the request.

        Args:
            param: The parameter object from function signature
            model_class: The expected model class (must be a Struct)
            _raw_body: Cached raw body data
            request: The Starlette request object

        Returns:
            Validated body data or JSONResponse with validation error
        """
        if not issubclass(model_class, Struct):
            raise TypeError(
                "Body type must be an instance of Tachyon_api.models.Struct"
            )

        decoder = msgspec.json.Decoder(model_class)
        try:
            if _raw_body is None:
                _raw_body = await request.body()
            validated_data = decoder.decode(_raw_body)
            return validated_data
        except msgspec.ValidationError as e:
            # Attempt to build field errors map using e.path
            field_errors = None
            try:
                path = getattr(e, "path", None)
                if path:
                    # Choose last string-ish path element as field name
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

    @staticmethod
    def process_query_parameter(param, query_params) -> Union[Any, JSONResponse, None]:
        """
        Process a Query parameter from the request.

        Args:
            param: The parameter object from function signature
            query_params: The query parameters from the request

        Returns:
            Converted parameter value, None (for missing optional), or JSONResponse with error
        """
        query_info = param.default
        param_name = param.name

        # Determine typing for advanced cases
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
                    return query_info.default
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
            return converted_list

        # Optional[T] handling for single value
        base_type, _is_opt = TypeUtils.unwrap_optional(ann)

        if param_name in query_params:
            value_str = query_params[param_name]
            converted_value = TypeConverter.convert_value(
                value_str, base_type, param_name, is_path_param=False
            )
            if isinstance(converted_value, JSONResponse):
                return converted_value
            return converted_value

        elif query_info.default is not ...:
            return query_info.default
        else:
            return validation_error_response(
                f"Missing required query parameter: {param_name}"
            )

    @staticmethod
    def process_explicit_path_parameter(param, path_params) -> Union[Any, JSONResponse]:
        """
        Process an explicit Path parameter (with Path() annotation).

        Args:
            param: The parameter object from function signature
            path_params: The path parameters from the request

        Returns:
            Converted parameter value or JSONResponse with error
        """
        param_name = param.name
        if param_name in path_params:
            value_str = path_params[param_name]
            # Support List[T] in path params via CSV
            ann = param.annotation
            origin = typing.get_origin(ann)
            args = typing.get_args(ann)
            if origin in (list, typing.List):
                item_type = args[0] if args else str
                parts = value_str.split(",") if value_str else []
                # Unwrap Optional for item type
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
                return converted_list
            else:
                converted_value = TypeConverter.convert_value(
                    value_str, ann, param_name, is_path_param=True
                )
                # Return 404 if conversion failed
                if isinstance(converted_value, JSONResponse):
                    return converted_value
                return converted_value
        else:
            return JSONResponse({"detail": "Not Found"}, status_code=404)

    @staticmethod
    def process_implicit_path_parameter(
        param, path_params
    ) -> Union[Any, JSONResponse, None]:
        """
        Process an implicit Path parameter (URL path variable without Path()).

        Args:
            param: The parameter object from function signature
            path_params: The path parameters from the request

        Returns:
            Converted parameter value, None (not processed), or JSONResponse with error
        """
        param_name = param.name
        value_str = path_params[param_name]
        # Support List[T] via CSV
        ann = param.annotation
        origin = typing.get_origin(ann)
        args = typing.get_args(ann)
        if origin in (list, typing.List):
            item_type = args[0] if args else str
            parts = value_str.split(",") if value_str else []
            # Unwrap Optional for item type
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
            return converted_list
        else:
            converted_value = TypeConverter.convert_value(
                value_str, ann, param_name, is_path_param=True
            )
            # Return 404 if conversion failed
            if isinstance(converted_value, JSONResponse):
                return converted_value
            return converted_value

    @classmethod
    async def process_parameter(
        cls,
        param,
        request,
        path_params,
        query_params,
        _raw_body,
        is_explicit_dependency,
        is_implicit_dependency,
    ) -> Union[Any, JSONResponse, None]:
        """
        Process a single parameter based on its type and annotations.

        Args:
            param: The parameter object from function signature
            request: The Starlette request object
            path_params: Path parameters from the request
            query_params: Query parameters from the request
            _raw_body: Cached raw body data
            is_explicit_dependency: Whether this is an explicit dependency
            is_implicit_dependency: Whether this is an implicit dependency

        Returns:
            Parameter value, JSONResponse (error), or None (not processed)
        """
        # Process Body parameters (JSON request body)
        if isinstance(param.default, Body):
            model_class = param.annotation
            result = await cls.process_body_parameter(
                param, model_class, _raw_body, request
            )
            return result

        # Process Query parameters (URL query string)
        elif isinstance(param.default, Query):
            result = cls.process_query_parameter(param, query_params)
            return result

        # Process explicit Path parameters (with Path() annotation)
        elif isinstance(param.default, Path):
            result = cls.process_explicit_path_parameter(param, path_params)
            return result

        # Process implicit Path parameters (URL path variables without Path())
        elif (
            param.default is inspect.Parameter.empty
            and param.name in path_params
            and not is_explicit_dependency
            and not is_implicit_dependency
        ):
            result = cls.process_implicit_path_parameter(param, path_params)
            return result

        # Parameter not processed by this processor
        return _NotProcessed()
