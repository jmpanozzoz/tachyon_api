# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled uploaded-file extractor."""

from starlette.datastructures import UploadFile as StarletteUploadFile
from ...files import UploadFile
from ...responses import validation_error_response
from ._missing import missing


cdef class FileExtractor:
    """Extracts an UploadFile from form data and validates all repeated multipart values."""

    cpdef extract(self, object descriptor, object form_data):
        cdef str name = descriptor.effective_name
        if name not in form_data:
            if descriptor.is_list and isinstance(descriptor.default, list):
                return (descriptor.default.copy(), None)
            return missing(descriptor, "file", name)

        uploads = form_data.getlist(name)
        if not descriptor.is_list and len(uploads) != 1:
            return (None, validation_error_response(f"Invalid file upload for: {name}"))
        for upload in uploads:
            if not isinstance(upload, StarletteUploadFile):
                return (None, validation_error_response(f"Invalid file upload for: {name}"))
        uploads = [UploadFile.from_starlette(upload) for upload in uploads]
        return (uploads if descriptor.is_list else uploads[0], None)
