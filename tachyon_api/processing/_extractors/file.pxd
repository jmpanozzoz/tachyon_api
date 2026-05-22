# cython: language_level=3
"""Public declaration of FileExtractor — enables `cimport` from parameters.pyx."""


cdef class FileExtractor:
    cpdef extract(self, object descriptor, object form_data)
