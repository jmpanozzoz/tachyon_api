# cython: language_level=3
"""Public declaration of CookieExtractor — enables `cimport` from parameters.pyx."""


cdef class CookieExtractor:
    cpdef extract(self, object descriptor, object request)
