"""
Path trie router with static priority and wildcard fallback.

Replaces Starlette's O(N × regex) linear route scan. Each static segment is
a dict lookup. Ambiguous branches backtrack when a static path dead-ends.

Path format: /users/{user_id}/profile  (Starlette / FastAPI convention)
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Callable, Dict, Optional, Set, Tuple


_NOT_FOUND          = 0
_METHOD_NOT_ALLOWED = 1
_FOUND              = 2

# Immutable empty sentinel — returned for routes with no path params.
# MappingProxyType prevents accidental mutation; safe because nobody writes to path_params.
_EMPTY_PARAMS = MappingProxyType({})


class _Node:
    """One node in the radix trie — represents one path segment."""

    __slots__ = ("static", "param_child", "param_names", "handlers", "allowed", "allow_header")

    def __init__(self) -> None:
        self.static: Dict[str, _Node] = {}       # segment text → child
        self.param_child: Optional[_Node] = None  # {name} wildcard child
        self.param_names: Dict[str, tuple] = {}    # names for each terminal method
        self.handlers: Dict[str, Callable] = {}   # METHOD → async handler
        self.allowed: Set[str] = set()            # all registered methods (for 405)
        self.allow_header: str = ""               # pre-sorted Allow header value, e.g. "GET, POST"


class RadixTrie:
    """
    Register routes at startup; prefer static paths with wildcard fallback.

    Usage:
        trie = RadixTrie()
        trie.add("/users/{id}", "GET", handler)
        status, handler, params, allowed = trie.match("/users/42", "GET")
    """

    __slots__ = ("_root", "_static_endings", "_dynamic_ending")

    def __init__(self) -> None:
        self._root = _Node()
        self._static_endings = set()
        self._dynamic_ending = False

    # ── Registration ────────────────────────────────────────────────────────

    def add(self, path: str, method: str, handler: Callable) -> None:
        """Register a (path, method) → handler mapping."""
        node = self._root
        names = []
        segments = _segments(path)
        last = segments[-1] if segments else ""
        if last.startswith("{") and last.endswith("}"):
            self._dynamic_ending = True
        else:
            self._static_endings.add(last)
        for seg in segments:
            if seg[0] == "{" and seg[-1] == "}":
                # Param segment — create param child if needed
                if node.param_child is None:
                    node.param_child = _Node()
                names.append(seg[1:-1])
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
        node.param_names[m] = tuple(names)
        node.allowed.add(m)
        # Keep Allow header pre-sorted — avoids sorted() on every 405 response
        node.allow_header = ", ".join(sorted(node.allowed))

    # ── Matching ─────────────────────────────────────────────────────────────

    def match(
        self, path: str, method: str
    ) -> Tuple[int, Optional[Callable], Dict[str, str], Optional[str]]:
        """
        Match path + method, backtracking only on ambiguous static branches.

        Returns (status, handler, path_params, allow_header):
        - status 0 (_NOT_FOUND):          no path match
        - status 1 (_METHOD_NOT_ALLOWED): path matched, method not registered
        - status 2 (_FOUND):              full match

        path_params is _EMPTY_PARAMS (MappingProxyType) for routes with no path
        parameters — avoids a dict allocation on every static-route request.
        """
        # Prefer the first complete static path, regardless of HTTP method.
        # A static dead end must not hide a complete wildcard route.
        node = self._root
        pos = 0
        values = ()
        alternatives = None
        length = len(path)
        while True:
            while pos < length and path[pos] == "/":
                pos += 1
            if pos == length:
                if node.allowed:
                    m = method.upper()
                    handler = node.handlers.get(m)
                    if handler is None:
                        return _METHOD_NOT_ALLOWED, None, _EMPTY_PARAMS, node.allow_header
                    names = node.param_names[m]
                    params = dict(zip(names, values)) if names else _EMPTY_PARAMS
                    return _FOUND, handler, params, None
            else:
                slash = path.find("/", pos)
                end = length if slash == -1 else slash
                seg = path[pos:end]
                child = node.static.get(seg)
                wildcard = node.param_child
                if child is not None:
                    if wildcard is not None:
                        if alternatives is None:
                            # Check only when ambiguity would create a search
                            # stack. Normal unambiguous hits pay no suffix scan.
                            if not self._dynamic_ending:
                                tail = path.rstrip("/")
                                tail = tail[tail.rfind("/") + 1:]
                                if tail not in self._static_endings:
                                    return _NOT_FOUND, None, _EMPTY_PARAMS, None
                            alternatives = []
                        alternatives.append((wildcard, end, values + (seg,)))
                    node = child
                    pos = end
                    continue
                if wildcard is not None:
                    node = wildcard
                    values = values + (seg,)
                    pos = end
                    continue
            if not alternatives:
                return _NOT_FOUND, None, _EMPTY_PARAMS, None
            node, pos, values = alternatives.pop()



def _segments(path: str):
    """Split a URL path into non-empty segments."""
    return [s for s in path.split("/") if s]
