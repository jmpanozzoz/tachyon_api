# HOT PATH — extracts a cookie value by name.

from ..compiler import ParamDescriptor
from ..scope import TachyonScope
from ._base import ExtractorResult
from ._missing import missing


class CookieExtractor:
    """Extracts a single cookie value by name."""

    __slots__ = ()

    def extract(self, descriptor: ParamDescriptor, request: TachyonScope) -> ExtractorResult:
        value = request.cookies.get(descriptor.effective_name)
        if value is not None:
            return ExtractorResult(value, None)
        return missing(descriptor, "cookie", descriptor.effective_name)
