# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled dependency-override lookup.

Sibling of `_override_lookup.py`. cdef class so attribute access (`self._app`)
goes through a C-level slot instead of a dict lookup.

Returns the resolved override value (invoking the override factory if callable)
or the module-level `_SENTINEL` if no override is registered.  Callers must
compare against `_SENTINEL` instead of `None` because `None` is a valid
override value.
"""

_SENTINEL = object()


cdef class OverrideLookup:
    """Answers: "is there a registered override for this dependency key?" """

    cdef object _app

    def __init__(self, app):
        self._app = app

    def lookup(self, key):
        overrides = self._app.dependency_overrides
        if key not in overrides:
            return _SENTINEL
        override = overrides[key]
        if callable(override):
            return override()
        return override
