# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled cookie extractor."""

from ._base import ExtractorResult
from ._missing import missing


cdef class CookieExtractor:
    """Extracts a single cookie value by name."""

    def extract(self, descriptor, request):
        value = request.cookies.get(descriptor.effective_name)
        if value is not None:
            return ExtractorResult(value, None)
        return missing(descriptor, "cookie", descriptor.effective_name)
