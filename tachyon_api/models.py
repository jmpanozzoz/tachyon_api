"""msgspec Struct + orjson-powered JSON encoding/decoding."""

import uuid
from typing import Any, Dict, Type, TypeVar, Optional, Union

import msgspec
import orjson
from msgspec import Struct

__all__ = ["Struct", "encode_json", "decode_json"]

T = TypeVar("T")


def _orjson_default(obj: Any) -> Any:
    """Default function for orjson to serialize types it doesn't support natively.

    datetime/date need no branch here — orjson serializes them natively under
    every option set.  UUID stays: it is only native with OPT_SERIALIZE_UUID,
    and callers may pass a custom `option` to encode_json without it.
    """
    if isinstance(obj, uuid.UUID):
        return str(obj)  # pragma: no cover — default opts include OPT_SERIALIZE_UUID
    if isinstance(obj, Struct):
        return msgspec.to_builtins(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


_ORJSON_OPTS = orjson.OPT_SERIALIZE_DATACLASS | orjson.OPT_SERIALIZE_UUID | orjson.OPT_UTC_Z


def encode_json(obj: Any, option: Optional[int] = None) -> bytes:
    return orjson.dumps(obj, default=_orjson_default, option=option or _ORJSON_OPTS)


def decode_json(data: Union[bytes, str], type_: Type[T] = Dict[str, Any]) -> T:
    if isinstance(data, str):
        data = data.encode("utf-8")
    parsed_data = orjson.loads(data)
    if isinstance(type_, type) and issubclass(type_, Struct):
        return msgspec.convert(parsed_data, type_)
    return parsed_data
