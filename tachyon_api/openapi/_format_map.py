# Python types that map to a specific OpenAPI `string` format.
# Consulted by ParamSchemaBuilder for scalar parameter types.

import datetime
import uuid
from typing import Dict, Tuple, Type

_OPENAPI_FORMAT_MAP: Dict[Type, Tuple[str, str]] = {
    datetime.datetime: ("string", "date-time"),
    datetime.date: ("string", "date"),
    uuid.UUID: ("string", "uuid"),
}
