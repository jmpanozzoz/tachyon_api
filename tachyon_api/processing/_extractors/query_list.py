# HOT PATH — extracts and converts a list-valued query parameter.
# Supports both repeated keys (?id=1&id=2) and CSV form (?id=1,2,3).

from starlette.responses import JSONResponse

from ..compiler import ParamDescriptor
from ...responses import validation_error_response
from ...utils import TypeConverter
from ._missing import missing

# DoS guard — caps the final list size after CSV expansion. v1.3.0 audit:
# ?ids=1,2,...,1000000 would otherwise allocate a million-element list.
MAX_QUERY_LIST_SIZE = 1000


class QueryListExtractor:
    """Extracts a list query parameter, handling repeated keys and CSV values."""

    __slots__ = ()

    def extract(self, descriptor: ParamDescriptor, query_params):
        """Returns `(value, error)` plain tuple."""
        name = descriptor.name

        raw_values = query_params.getlist(name)
        if not raw_values and name in query_params:
            raw_values = [query_params[name]]

        values: list = []
        for v in raw_values:
            if isinstance(v, str) and "," in v:
                values.extend(v.split(","))
            else:
                values.append(v)
            if len(values) > MAX_QUERY_LIST_SIZE:
                return (None, validation_error_response(
                    f"Query parameter '{name}' exceeds maximum list size "
                    f"({MAX_QUERY_LIST_SIZE} items)"
                ))

        if not values:
            return missing(descriptor, "query parameter", name)

        converted = TypeConverter.convert_list_values_bare(
            values,
            descriptor.item_type,
            descriptor.item_is_optional,
            name,
            is_path_param=False,
        )
        if isinstance(converted, JSONResponse):
            return (None, converted)
        return (converted, None)
