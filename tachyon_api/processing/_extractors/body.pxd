# cython: language_level=3
"""Public declaration of BodyExtractor — enables `cimport` from parameters.pyx.

`extract` is `async def`, not `cpdef`, because Cython does not expose async
methods through cpdef.  Cross-module dispatch on the call still goes through
Python machinery, but it's dominated by `await request.body()` I/O — typing
the attribute via cimport still wins by skipping the per-call attribute
lookup on `self._body_extractor`.
"""

from .body_limit cimport BodySizeChecker


cdef class BodyExtractor:
    cdef BodySizeChecker _size_check
