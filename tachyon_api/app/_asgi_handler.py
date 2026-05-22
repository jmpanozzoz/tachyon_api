# HOT PATH — cdef migration target for v1.3.x.
# Marker class for handlers that take (scope, receive, send) directly,
# skipping Request object creation in the trie dispatch path.

from typing import Callable


class _ASGIHandler:
    """Marks a handler that takes (scope, receive, send) directly."""

    __slots__ = ("fn",)  # Callable → cdef object

    def __init__(self, fn: Callable) -> None:
        self.fn = fn
