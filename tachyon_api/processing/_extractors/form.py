# HOT PATH — extracts a single form field from already-materialized form data.

from ..compiler import ParamDescriptor
from ._base import ExtractorResult
from ._missing import missing


class FormExtractor:
    """Extracts a single form-field value."""

    __slots__ = ()

    def extract(self, descriptor: ParamDescriptor, form_data) -> ExtractorResult:
        name = descriptor.effective_name
        if name in form_data:
            return ExtractorResult(form_data[name], None)
        return missing(descriptor, "form field", name)
