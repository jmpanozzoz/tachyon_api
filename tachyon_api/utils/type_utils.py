"""
Tachyon API - Type Utilities

This module provides utility functions for working with Python types,
particularly for handling Optional types, Union types, and generic types
used throughout the Tachyon framework.
"""

import typing
from typing import Type, Tuple, Union


class TypeUtils:
    """
    Utility class for type inspection and manipulation.

    Provides static methods to analyze Python type annotations,
    particularly useful for handling Optional[T], Union types,
    and generic types in parameter processing.
    """

    @staticmethod
    def unwrap_optional(python_type: Type) -> Tuple[Type, bool]:
        """
        Unwrap Optional[T] types to get the inner type and optionality flag.

        This method analyzes a type annotation and determines if it represents
        an Optional type (Union[T, None]). It returns the inner type and a
        boolean indicating whether the type is optional.

        Args:
            python_type: The type annotation to analyze

        Returns:
            Tuple containing:
            - inner_type: The unwrapped type (T from Optional[T])
            - is_optional: Boolean indicating if the type was Optional

        Examples:
            >>> TypeUtils.unwrap_optional(Optional[str])
            (str, True)
            >>> TypeUtils.unwrap_optional(str)
            (str, False)
            >>> TypeUtils.unwrap_optional(Union[int, None])
            (int, True)
        """
        origin = typing.get_origin(python_type)
        args = typing.get_args(python_type)

        if origin is Union and args:
            non_none = [a for a in args if a is not type(None)]  # noqa: E721
            if len(non_none) == 1:
                return non_none[0], True

        return python_type, False

    @staticmethod
    def is_list_type(python_type: Type) -> Tuple[bool, Type]:
        """
        Check if a type is a List type and extract the item type.

        Args:
            python_type: The type annotation to check

        Returns:
            Tuple containing:
            - is_list: Boolean indicating if the type is a List
            - item_type: The type of list items (str if not a list or no args)

        Examples:
            >>> TypeUtils.is_list_type(List[str])
            (True, str)
            >>> TypeUtils.is_list_type(str)
            (False, str)
        """
        origin = typing.get_origin(python_type)
        args = typing.get_args(python_type)

        if origin in (list, typing.List):
            item_type = args[0] if args else str
            return True, item_type

        return False, str

    @staticmethod
    def get_type_name(python_type: Type) -> str:
        """
        Get a human-readable name for a type.

        Args:
            python_type: The type to get the name for

        Returns:
            Human-readable type name

        Examples:
            >>> TypeUtils.get_type_name(int)
            'integer'
            >>> TypeUtils.get_type_name(str)
            'string'
        """
        if python_type is int:
            return "integer"
        elif python_type is str:
            return "string"
        elif python_type is bool:
            return "boolean"
        elif python_type is float:
            return "number"
        else:
            return getattr(python_type, "__name__", str(python_type))
