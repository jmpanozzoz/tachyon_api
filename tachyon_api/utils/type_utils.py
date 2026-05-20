"""Centralized type inspection utilities for Optional, List, and OpenAPI type mapping."""

import typing
from typing import Type, Tuple, Union, Dict, Any

OPENAPI_TYPE_MAP: Dict[Type, str] = {
    int: "integer",
    str: "string",
    bool: "boolean",
    float: "number",
}


class TypeUtils:
    @staticmethod
    def unwrap_optional(python_type: Type) -> Tuple[Type, bool]:
        """Return (inner_type, is_optional) for Optional[T], else (type, False)."""
        origin = typing.get_origin(python_type)
        args = typing.get_args(python_type)
        if origin is Union and args:
            non_none = [a for a in args if a is not type(None)]  # noqa: E721
            if len(non_none) == 1:
                return non_none[0], True
        return python_type, False

    @staticmethod
    def is_list_type(python_type: Type) -> Tuple[bool, Type]:
        """Return (True, item_type) for List[T], else (False, str)."""
        origin = typing.get_origin(python_type)
        args = typing.get_args(python_type)
        if origin in (list, typing.List):
            return True, args[0] if args else str
        return False, str

    @staticmethod
    def get_type_name(python_type: Type) -> str:
        return OPENAPI_TYPE_MAP.get(
            python_type, getattr(python_type, "__name__", str(python_type))
        )

    @staticmethod
    def get_openapi_type(python_type: Type) -> str:
        return OPENAPI_TYPE_MAP.get(python_type, "string")

    @staticmethod
    def normalize_header_name(param_name: str) -> str:
        """Convert a Python param name to its canonical HTTP header name (underscore → hyphen, lowercase)."""
        return param_name.replace("_", "-").lower()

    @staticmethod
    def get_origin(python_type: Type) -> Any:
        return typing.get_origin(python_type)

    @staticmethod
    def get_args(python_type: Type) -> Tuple:
        return typing.get_args(python_type)
