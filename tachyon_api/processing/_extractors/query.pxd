# cython: language_level=3
"""Public declaration of QueryExtractor — enables `cimport` from parameters.pyx."""


cdef class QueryExtractor:
    cpdef extract(self, object descriptor, object query_params)
