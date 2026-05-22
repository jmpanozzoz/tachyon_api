# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled header extractor.

Sibling of `header.py`. cdef class — single attribute (none) but the
method body gets Cython byte-code compilation.
"""

from ._base import ExtractorResult
from ._missing import missing


cdef class HeaderExtractor:
    """Extracts a single header value by its canonical name."""

    def extract(self, descriptor, request):
        value = request.headers.get(descriptor.effective_name)
        if value is not None:
            return ExtractorResult(value, None)
        return missing(descriptor, "header", descriptor.effective_name)
