# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled uploaded-file extractor."""

from ...responses import validation_error_response
from ._missing import missing


cdef class FileExtractor:
    """Extracts an UploadFile from form data and validates the filename attribute."""

    cpdef extract(self, object descriptor, object form_data):
        cdef str name = descriptor.effective_name
        if name not in form_data:
            return missing(descriptor, "file", name)

        uploaded = form_data[name]
        if hasattr(uploaded, "filename"):
            return (uploaded, None)

        # Present but not a file — fall back to default or 422
        if descriptor.default is not ...:
            return (descriptor.default, None)
        return (None, validation_error_response(f"Invalid file upload for: {name}"))
