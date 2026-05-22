# Construction-time — instantiates an @injectable class by resolving its
# constructor dependencies recursively through the supplied resolver callback.

import inspect
from typing import Any, Callable, Dict, Optional, Type

from ._sig_cache import get_signature


class ClassFactory:
    """Builds a class instance by resolving every typed constructor parameter."""

    __slots__ = ("_resolve_dep",)

    def __init__(
        self, resolve_dep: Callable[[Type, Optional[Dict]], Any]
    ) -> None:
        self._resolve_dep = resolve_dep

    def build(self, cls: Type, request_cache: Optional[Dict]) -> Any:
        sig = get_signature(cls)
        nested: Dict[str, Any] = {}
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
