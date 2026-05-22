# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled class-dep instantiator.

Sibling of `_class_factory.py`.  Builds an `@injectable` class instance by
resolving its constructor dependencies recursively through the supplied
resolver callback.
"""

import inspect

from ._sig_cache import get_signature


cdef class ClassFactory:
    """Builds a class instance by resolving every typed constructor parameter."""

    cdef object _resolve_dep

    def __init__(self, resolve_dep):
        # resolve_dep is the recursive resolver (DependencyResolver.resolve_dependency)
        self._resolve_dep = resolve_dep

    def build(self, cls, request_cache):
        sig = get_signature(cls)
        cdef dict nested = {}
        for param in sig.parameters.values():
            if param.name == "self":
                continue
            if param.annotation is inspect.Parameter.empty:
                raise TypeError(
                    f"Parameter '{param.name}' in '{cls.__name__}' has no type annotation; "
                    f"cannot resolve dependency."
                )
            nested[param.name] = self._resolve_dep(param.annotation, request_cache)
        return cls(**nested)
