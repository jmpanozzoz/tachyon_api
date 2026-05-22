# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled scalar query extractor."""

from starlette.responses import JSONResponse

from ...utils import TypeConverter
from ._base import ExtractorResult
from ._missing import missing


cdef class QueryExtractor:
    """Extracts a single scalar query parameter and converts to its declared type."""

    def extract(self, descriptor, query_params):
        cdef str name = descriptor.name
        if name not in query_params:
            return missing(descriptor, "query parameter", name)

        converted = TypeConverter.convert_value_bare(
            query_params[name], descriptor.base_type, name, is_path_param=False
        )
        if isinstance(converted, JSONResponse):
            return ExtractorResult(None, converted)
        return ExtractorResult(converted, None)
