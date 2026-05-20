"""
Radix trie router — O(k) path matching where k = number of path segments.

Replaces Starlette's O(N × regex) linear route scan. Each static segment is
a dict lookup; each param segment is a single branch check.

Path format: /users/{user_id}/profile  (Starlette / FastAPI convention)
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Set, Tuple, Any


_NOT_FOUND          = 0
_METHOD_NOT_ALLOWED = 1
_FOUND              = 2


class _Node:
    """One node in the radix trie — represents one path segment."""

    __slots__ = ("static", "param_child", "param_name", "handlers", "allowed")

    def __init__(self) -> None:
        self.static: Dict[str, _Node] = {}       # segment text → child
        self.param_child: Optional[_Node] = None  # {name} wildcard child
        self.param_name: Optional[str] = None     # name extracted from {name}
        self.handlers: Dict[str, Callable] = {}   # METHOD → async handler
        self.allowed: Set[str] = set()            # all registered methods (for 405)


class RadixTrie:
    """
    Register routes at startup, match in O(k) per request.

    Usage:
        trie = RadixTrie()
        trie.add("/users/{id}", "GET", handler)
        status, handler, params, allowed = trie.match("/users/42", "GET")
    """

    __slots__ = ("_root",)

    def __init__(self) -> None:
        self._root = _Node()

    # ── Registration ────────────────────────────────────────────────────────

    def add(self, path: str, method: str, handler: Callable) -> None:
        """Register a (path, method) → handler mapping."""
        node = self._root
        for seg in _segments(path):
            if seg[0] == "{" and seg[-1] == "}":
                # Param segment — create param child if needed
                if node.param_child is None:
                    node.param_child = _Node()
                    node.param_child.param_name = seg[1:-1]
                node = node.param_child
            else:
                # Static segment — O(1) dict lookup/insert
                child = node.static.get(seg)
                if child is None:
                    child = _Node()
                    node.static[seg] = child
                node = child

        m = method.upper()
        node.handlers[m] = handler
        node.allowed.add(m)

    # ── Matching ─────────────────────────────────────────────────────────────

    def match(
        self, path: str, method: str
    ) -> Tuple[int, Optional[Callable], Dict[str, str], Optional[Set[str]]]:
        """
        Match path + method.

        Returns (status, handler, path_params, allowed_methods):
        - status 0 (_NOT_FOUND):          no path match
        - status 1 (_METHOD_NOT_ALLOWED): path matched, method not registered
        - status 2 (_FOUND):              full match
        """
        node = self._root
        path_params: Dict[str, str] = {}

        for seg in _segments(path):
            child = node.static.get(seg)
            if child is not None:
                node = child
            elif node.param_child is not None:
                path_params[node.param_child.param_name] = seg
                node = node.param_child
            else:
                return _NOT_FOUND, None, {}, None

        handler = node.handlers.get(method.upper())
        if handler is not None:
            return _FOUND, handler, path_params, None

        if node.allowed:
            return _METHOD_NOT_ALLOWED, None, path_params, node.allowed

        return _NOT_FOUND, None, {}, None


def _segments(path: str):
    """Split a URL path into non-empty segments."""
    return [s for s in path.split("/") if s]
