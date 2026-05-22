# HOT PATH — extracts and converts a list-valued query parameter.
# Supports both repeated keys (?id=1&id=2) and CSV form (?id=1,2,3).

from starlette.responses import JSONResponse

from ..compiler import ParamDescriptor
from ...utils import TypeConverter
from ._missing import missing


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
