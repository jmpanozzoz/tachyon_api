# cython: language_level=3
"""Public declaration of FormExtractor — enables `cimport` from parameters.pyx."""


cdef class FormExtractor:
    cpdef extract(self, object descriptor, object form_data)
