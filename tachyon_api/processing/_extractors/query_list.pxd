# cython: language_level=3
"""Public declaration of QueryListExtractor — enables `cimport` from parameters.pyx."""


cdef class QueryListExtractor:
    cpdef extract(self, object descriptor, object query_params)
