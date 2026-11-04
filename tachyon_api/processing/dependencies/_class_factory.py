# Construction-time — instantiates an @injectable class by resolving its
# constructor dependencies recursively through the supplied resolver callback.

from typing import Any, Callable, Dict, Optional, Type

from ...di import _registry
from ._sig_cache import get_bindings


class ClassFactory:
    """Builds a class instance by resolving every typed constructor parameter."""

    __slots__ = ("_resolve_dep",)

    def __init__(
        self, resolve_dep: Callable[[Type, Optional[Dict]], Any]
    ) -> None:
        self._resolve_dep = resolve_dep

    def build(self, cls: Type, request_cache: Optional[Dict]) -> Any:
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
