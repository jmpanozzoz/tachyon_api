# HOT PATH — extracts a single form field from already-materialized form data.

from ..compiler import ParamDescriptor
from ._missing import missing


class FormExtractor:
    """Extracts a single form-field value."""

    __slots__ = ()

    def extract(self, descriptor: ParamDescriptor, form_data):
        """Returns `(value, error)` plain tuple."""
        name = descriptor.effective_name
        if name in form_data:
            return (form_data[name], None)
        return missing(descriptor, "form field", name)
