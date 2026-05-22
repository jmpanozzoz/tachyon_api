# HOT PATH — extracts and type-converts a scalar query parameter.

from starlette.responses import JSONResponse

from ..compiler import ParamDescriptor
from ...utils import TypeConverter
from ._missing import missing


class QueryExtractor:
    """Extracts a single scalar query parameter and converts to its declared type."""

    __slots__ = ()

    def extract(self, descriptor: ParamDescriptor, query_params):
        """Returns `(value, error)` plain tuple."""
        name = descriptor.name
        if name not in query_params:
            return missing(descriptor, "query parameter", name)

        converted = TypeConverter.convert_value_bare(
            query_params[name], descriptor.base_type, name, is_path_param=False
        )
        if isinstance(converted, JSONResponse):
            return (None, converted)
        return (converted, None)
