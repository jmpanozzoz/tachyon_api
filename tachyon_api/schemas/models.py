"""
Tachyon Web Framework - Data Models Module

This module provides the base model class for request/response data validation
using msgspec for high-performance JSON serialization and validation.
The module enhances msgspec with orjson for even faster JSON processing.
"""

import datetime
import uuid
from typing import Any, Dict, Type, TypeVar, Optional, Union

import msgspec
import orjson
from msgspec import Struct, Meta

__all__ = ["Struct", "Meta", "encode_json", "decode_json"]

T = TypeVar("T")


def _orjson_default(obj: Any) -> Any:
    """Default function for orjson to serialize types it doesn't support natively."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Struct):
        return msgspec.to_builtins(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def encode_json(obj: Any, option: Optional[int] = None) -> bytes:
    """
    Encode a Python object to JSON using orjson.

    Args:
        obj: Object to encode (can be a Struct instance or any JSON-serializable object)
        option: orjson option flags (e.g., orjson.OPT_INDENT_2)

    Returns:
        JSON-encoded bytes
    """
    opts = (
        option
        or orjson.OPT_SERIALIZE_DATACLASS | orjson.OPT_SERIALIZE_UUID | orjson.OPT_UTC_Z
    )
    return orjson.dumps(obj, default=_orjson_default, option=opts)


def decode_json(data: Union[bytes, str], type_: Type[T] = Dict[str, Any]) -> T:
    """
    Decode JSON to a Python object using orjson.
    If a Struct type is provided, the decoded data will be converted to that type.

    Args:
        data: JSON data as bytes or string
        type_: Target type (default is Dict[str, Any])

    Returns:
        Decoded object of the specified type
    """
    if isinstance(data, str):
        data = data.encode("utf-8")

    # First use orjson for fast JSON parsing
    parsed_data = orjson.loads(data)

    # If the target type is a Struct or similar msgspec type, use msgspec.convert
    if isinstance(type_, type) and issubclass(type_, Struct):
        return msgspec.convert(parsed_data, type_)

    return parsed_data
