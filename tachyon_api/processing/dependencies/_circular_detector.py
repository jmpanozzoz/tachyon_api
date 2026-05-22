# Hot path during construction — tracks in-flight class instantiations to
# detect circular dependencies before they overflow the call stack.

from typing import Set, Type


class CircularDetector:
    """Tracks classes currently being resolved; raises on cycle."""

    __slots__ = ("_resolving",)

    def __init__(self) -> None:
        self._resolving: Set[Type] = set()

    def check_and_enter(self, cls: Type) -> None:
        if cls in self._resolving:
            raise TypeError(
                f"Circular dependency detected while resolving '{cls.__name__}'"
            )
        self._resolving.add(cls)

    def exit(self, cls: Type) -> None:
        self._resolving.discard(cls)
