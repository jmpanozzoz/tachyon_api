"""msgspec Struct + orjson-powered JSON encoding/decoding."""

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
    opts = option or orjson.OPT_SERIALIZE_DATACLASS | orjson.OPT_SERIALIZE_UUID | orjson.OPT_UTC_Z
    return orjson.dumps(obj, default=_orjson_default, option=opts)


def decode_json(data: Union[bytes, str], type_: Type[T] = Dict[str, Any]) -> T:
    if isinstance(data, str):
        data = data.encode("utf-8")
    parsed_data = orjson.loads(data)
    if isinstance(type_, type) and issubclass(type_, Struct):
        return msgspec.convert(parsed_data, type_)
    return parsed_data
