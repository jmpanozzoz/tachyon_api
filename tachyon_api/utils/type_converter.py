"""
Tachyon API - Type Converter

This module provides functionality for converting string values to appropriate Python types
with proper error handling. Used primarily for converting URL parameters and query strings
to typed values expected by endpoint functions.
"""

from typing import Type, Union, Any
from starlette.responses import JSONResponse

from ..responses import validation_error_response
from .type_utils import TypeUtils


class TypeConverter:
    """
    Handles conversion of string values to target Python types.

    This class provides methods to convert string representations of values
    (typically from URL parameters or query strings) to their appropriate
    Python types with comprehensive error handling.
    """

    @staticmethod
    def convert_value(
        value_str: str,
        target_type: Type,
        param_name: str,
        is_path_param: bool = False,
    ) -> Union[Any, JSONResponse]:
        """
        Convert a string value to the target type with appropriate error handling.

        This method handles type conversion for query and path parameters,
        including special handling for boolean values and proper error responses.

        Args:
            value_str: The string value to convert
            target_type: The target Python type to convert to
            param_name: Name of the parameter (for error messages)
            is_path_param: Whether this is a path parameter (affects error response)

        Returns:
            The converted value, or a JSONResponse with appropriate error code

        Note:
            - Boolean conversion accepts: "true", "1", "t", "yes" (case-insensitive)
            - Path parameter errors return 404, query parameter errors return 422

        Examples:
            >>> TypeConverter.convert_value("123", int, "limit")
            123
            >>> TypeConverter.convert_value("true", bool, "active")
            True
            >>> TypeConverter.convert_value("invalid", int, "limit")
            JSONResponse({"success": False, "error": "Invalid value for integer conversion", ...})
        """
        # Unwrap Optional/Union[T, None]
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
                type_name = TypeUtils.get_type_name(target_type)
                return validation_error_response(
                    f"Invalid value for {type_name} conversion"
                )

    @staticmethod
    def convert_list_values(
        values: list[str], item_type: Type, param_name: str, is_path_param: bool = False
    ) -> Union[list[Any], JSONResponse]:
        """
        Convert a list of string values to the target item type.

        Args:
            values: List of string values to convert
            item_type: Target type for each item
            param_name: Parameter name for error messages
            is_path_param: Whether this is a path parameter

        Returns:
            List of converted values or error response
        """
        base_item_type, item_is_optional = TypeUtils.unwrap_optional(item_type)
        converted_list = []

        for value_str in values:
            # Handle null/empty values for optional items
            if item_is_optional and (value_str == "" or value_str.lower() == "null"):
                converted_list.append(None)
                continue

            converted_value = TypeConverter.convert_value(
                value_str, base_item_type, param_name, is_path_param
            )

            # If conversion failed, return the error response
            if isinstance(converted_value, JSONResponse):
                return converted_value

            converted_list.append(converted_value)

        return converted_list
