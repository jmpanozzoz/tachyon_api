# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled form-field extractor."""

from ._missing import missing


cdef class FormExtractor:
    """Extracts a single form-field value."""

    cpdef extract(self, object descriptor, object form_data):
        cdef str name = descriptor.effective_name
        if name in form_data:
            return (form_data[name], None)
        return missing(descriptor, "form field", name)
