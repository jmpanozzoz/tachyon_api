# cython: language_level=3
"""Public declaration of PathExtractor — enables `cimport` from parameters.pyx."""


cdef class PathExtractor:
    cpdef extract(self, object descriptor, object path_params)
