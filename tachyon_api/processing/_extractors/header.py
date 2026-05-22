# HOT PATH — extracts a request header by its canonical (kebab-case) name.

from ..compiler import ParamDescriptor
from ..scope import TachyonScope
from ._base import ExtractorResult
from ._missing import missing


class HeaderExtractor:
    """Extracts a single header value by its canonical name."""

    __slots__ = ()

    def extract(self, descriptor: ParamDescriptor, request: TachyonScope) -> ExtractorResult:
        value = request.headers.get(descriptor.effective_name)
        if value is not None:
            return ExtractorResult(value, None)
        return missing(descriptor, "header", descriptor.effective_name)
