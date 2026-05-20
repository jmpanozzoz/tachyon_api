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
        """Convert a string value to target_type. Handles Optional[T] by unwrapping first."""
        target_type, _ = TypeUtils.unwrap_optional(target_type)
        return TypeConverter._convert_bare(value_str, target_type, param_name, is_path_param)

    @staticmethod
    def convert_value_bare(
        value_str: str,
        base_type: Type,
        param_name: str,
        is_path_param: bool = False,
    ) -> Union[Any, JSONResponse]:
        """Like convert_value but skips Optional unwrapping (caller already has base_type)."""
        return TypeConverter._convert_bare(value_str, base_type, param_name, is_path_param)

    @staticmethod
    def _convert_bare(
        value_str: str,
        base_type: Type,
        param_name: str,
        is_path_param: bool,
    ) -> Union[Any, JSONResponse]:
        try:
            if base_type is bool:
                return value_str.lower() in ("true", "1", "t", "yes")
            if base_type is not str:
                return base_type(value_str)
            return value_str
        except (ValueError, TypeError):
            if is_path_param:
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            return validation_error_response(
                f"Invalid value for {TypeUtils.get_type_name(base_type)} conversion"
            )

    @staticmethod
    def convert_list_values(
        values: list[str], item_type: Type, param_name: str, is_path_param: bool = False
    ) -> Union[list[Any], JSONResponse]:
        """Convert a list of strings. item_type may be Optional[T] — unwraps once."""
        base_item_type, item_is_optional = TypeUtils.unwrap_optional(item_type)
        return TypeConverter._convert_list_bare(
            values, base_item_type, item_is_optional, param_name, is_path_param
        )

    @staticmethod
    def convert_list_values_bare(
        values: list[str], base_item_type: Type, item_is_optional: bool,
        param_name: str, is_path_param: bool = False
    ) -> Union[list[Any], JSONResponse]:
        """Like convert_list_values but skips Optional unwrapping."""
        return TypeConverter._convert_list_bare(
            values, base_item_type, item_is_optional, param_name, is_path_param
        )

    @staticmethod
    def _convert_list_bare(
        values: list[str], base_type: Type, is_optional: bool,
        param_name: str, is_path_param: bool
    ) -> Union[list[Any], JSONResponse]:
        result = []
        for v in values:
            if is_optional and (v == "" or v.lower() == "null"):
                result.append(None)
                continue
            converted = TypeConverter._convert_bare(v, base_type, param_name, is_path_param)
            if isinstance(converted, JSONResponse):
                return converted
            result.append(converted)
        return result
