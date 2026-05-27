# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled circular-dependency detector.

Sibling of `_circular_detector.py`. cdef class so `_resolving` is a C-level
slot (set ops are unchanged but attribute access is faster).
"""


cdef class CircularDetector:
    """Tracks classes currently being resolved; raises on cycle."""

    cdef public set _resolving

    def __init__(self):
        self._resolving = set()

    def check_and_enter(self, cls):
        if cls in self._resolving:
            raise TypeError(
                f"Circular dependency detected while resolving '{cls.__name__}'"
            )
        self._resolving.add(cls)

    def exit(self, cls):
        self._resolving.discard(cls)
