"""String-to-type conversion for URL/query parameters."""

from typing import Type, Union, Any
from starlette.responses import JSONResponse

from ..responses import validation_error_response
from .type_utils import TypeUtils


class TypeConverter:
    @staticmethod
    def convert_value(
        value_str: str,
        target_type: Type,
        param_name: str,
        is_path_param: bool = False,
    ) -> Union[Any, JSONResponse]:
        target_type, _ = TypeUtils.unwrap_optional(target_type)
        try:
            if target_type is bool:
                return value_str.lower() in ("true", "1", "t", "yes")
            elif target_type is not str:
                return target_type(value_str)
            else:
                return value_str
        except (ValueError, TypeError):
            if is_path_param:
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            else:
                return validation_error_response(
                    f"Invalid value for {TypeUtils.get_type_name(target_type)} conversion"
                )

    @staticmethod
    def convert_list_values(
        values: list[str], item_type: Type, param_name: str, is_path_param: bool = False
    ) -> Union[list[Any], JSONResponse]:
        base_item_type, item_is_optional = TypeUtils.unwrap_optional(item_type)
        converted_list = []
        for value_str in values:
            if item_is_optional and (value_str == "" or value_str.lower() == "null"):
                converted_list.append(None)
                continue
            converted_value = TypeConverter.convert_value(
                value_str, base_item_type, param_name, is_path_param
            )
            if isinstance(converted_value, JSONResponse):
                return converted_value
            converted_list.append(converted_value)
        return converted_list
