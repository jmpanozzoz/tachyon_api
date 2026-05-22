# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled scope-aware class-dep cache.

Sibling of `_scope_cache.py`.  cdef class.  Indexes the per-class instances
according to the declared scope (singleton / request / transient).
"""

from ...di import SCOPE_REQUEST, SCOPE_SINGLETON, _scopes


cdef class ScopeCache:
    """Looks up and stores class instances according to their declared scope."""

    cdef object _app

    def __init__(self, app):
        self._app = app

    @staticmethod
    def get_scope(cls):
        return _scopes.get(cls, SCOPE_SINGLETON)

    def lookup(self, cls, scope, request_cache):
        if scope == SCOPE_SINGLETON:
            return self._app.get_instance(cls)
        if scope == SCOPE_REQUEST and request_cache is not None:
            return request_cache.get(cls)
        # SCOPE_TRANSIENT — never cached
        return None

    def store(self, cls, instance, scope, request_cache):
        if scope == SCOPE_SINGLETON:
            self._app.register_instance(cls, instance)
        elif scope == SCOPE_REQUEST and request_cache is not None:
            request_cache[cls] = instance
        # SCOPE_TRANSIENT — no-op
