# cython: language_level=3
"""Public declaration of HeaderExtractor — enables `cimport` from parameters.pyx.

A `cpdef` method visible at C level means callers can do a direct extension-type
slot call instead of going through Python's method dispatch.  Phase 4b.2 left
the call going through Python (`cdef object` reference + `def extract`); this
recovers the ~30-60 ns/call overhead.
"""


cdef class HeaderExtractor:
    cpdef extract(self, object descriptor, object request)
