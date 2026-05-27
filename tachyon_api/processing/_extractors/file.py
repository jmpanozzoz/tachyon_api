# HOT PATH — extracts an uploaded file from form data.

from ..compiler import ParamDescriptor
from ...responses import validation_error_response
from ._missing import missing


class FileExtractor:
    """Extracts an UploadFile from form data and validates it has a filename attribute."""

    __slots__ = ()

    def extract(self, descriptor: ParamDescriptor, form_data):
        """Returns `(value, error)` plain tuple."""
        name = descriptor.effective_name
        if name not in form_data:
            return missing(descriptor, "file", name)

        uploaded = form_data[name]
        if hasattr(uploaded, "filename"):
            return (uploaded, None)

        # Value is present but not a file — fall back to default or 422
        if descriptor.default is not ...:
            return (descriptor.default, None)
        return (None, validation_error_response(f"Invalid file upload for: {name}"))
