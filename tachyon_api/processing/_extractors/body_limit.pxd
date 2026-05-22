# cython: language_level=3
"""Public declaration of BodySizeChecker — enables `cimport` from body.pyx."""


cdef class BodySizeChecker:
    cdef Py_ssize_t _max

    cpdef check_content_length(self, object request)
    cpdef check_body_length(self, bytes body)
    cdef inline object _too_large_response(self)
