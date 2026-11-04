# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled class-dep instantiator.

Sibling of `_class_factory.py`.  Builds an `@injectable` class instance by
resolving its constructor dependencies recursively through the supplied
resolver callback.
"""

from ...di import _registry
from ._sig_cache import get_bindings


cdef class ClassFactory:
    """Builds a class instance by resolving every typed constructor parameter."""

    cdef object _resolve_dep

    def __init__(self, resolve_dep):
        # resolve_dep is the recursive resolver (DependencyResolver.resolve_dependency)
        self._resolve_dep = resolve_dep

    def build(self, cls, request_cache):
        args = []
        kwargs = {}
        for name, positional, kind, target in get_bindings(cls):
            if kind == "dependency":
                if target not in _registry:
                    raise TypeError("Callable constructor dependencies require asynchronous resolution")
                value = self._resolve_dep(target, request_cache)
            elif kind in ("request", "marker"):
                raise TypeError("Request constructor parameters require asynchronous resolution")
            else:
                value = target
            if positional:
                args.append(value)
            else:
                kwargs[name] = value
        return cls(*args, **kwargs)
