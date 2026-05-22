# cython: language_level=3
"""
Cython-compiled radix trie router.

cdef class _Node: C struct fields — static/param_child/handlers are direct field
reads rather than Python dict-based attribute lookups.

match() inlines segment traversal at C level — no _segments() list, no generator.
path_params dict is only allocated when the first param segment is actually hit.
"""
from types import MappingProxyType

_NOT_FOUND          = 0
_METHOD_NOT_ALLOWED = 1
_FOUND              = 2

# Immutable empty sentinel — returned for static routes (no path params).
# One allocation at module load; zero per request on static routes.
_EMPTY_PARAMS = MappingProxyType({})


cdef class _Node:
    """One trie node. cdef public fields give C-level field access."""

    cdef public dict   static
    cdef public object param_child
    cdef public object param_name
    cdef public dict   handlers
    cdef public object allowed       # set[str] — for add() bookkeeping
    cdef public str    allow_header  # pre-sorted "GET, POST" string for 405 responses

    def __init__(self):
        self.static       = {}
        self.param_child  = None
        self.param_name   = None
        self.handlers     = {}
        self.allowed      = set()
        self.allow_header = ""


cdef class RadixTrie:
    """O(k) trie router — k = path segment count (typically 2–5)."""

    cdef public _Node _root

    def __init__(self):
        self._root = _Node()

    def add(self, path, method, handler):
        """Register (path, method) → handler at startup."""
        cdef _Node node = self._root
        cdef _Node child

        for seg in _segments(path):
            # Use Python string methods — avoids Cython str indexing quirks
            if seg.startswith("{") and seg.endswith("}"):
                if node.param_child is None:
                    node.param_child = _Node()
                    (<_Node>node.param_child).param_name = seg[1:-1]
                node = <_Node>node.param_child
            else:
                existing = node.static.get(seg)
                if existing is None:
                    child = _Node()
                    node.static[seg] = child
                    node = child
                else:
                    node = <_Node>existing

        m = method.upper()
        node.handlers[m] = handler
        node.allowed.add(m)
        node.allow_header = ", ".join(sorted(node.allowed))

    def match(self, str path, str method):
        """
        Match path + method in O(k).

        Inlines segment traversal — no _segments() list, no generator overhead.
        path_params is lazily allocated: None until the first param segment is hit,
        _EMPTY_PARAMS (immutable singleton) when the route has no path parameters.
        """
        cdef _Node node = self._root
        cdef dict path_params = None
        cdef int pos, slash_pos, path_len
        cdef str seg
        cdef object existing

        path_len = len(path)
        pos = 1 if path_len > 0 and path[0] == "/" else 0

        while pos < path_len:
            slash_pos = path.find("/", pos)
            if slash_pos == -1:
                seg = path[pos:]
                pos = path_len
            else:
                seg = path[pos:slash_pos]
                pos = slash_pos + 1

            if not seg:
                continue

            existing = node.static.get(seg)
            if existing is not None:
                node = <_Node>existing
            elif node.param_child is not None:
                if path_params is None:
                    path_params = {}
                path_params[(<_Node>node.param_child).param_name] = seg
                node = <_Node>node.param_child
            else:
                return 0, None, _EMPTY_PARAMS, None  # _NOT_FOUND

        handler = node.handlers.get(method.upper())
        if handler is not None:
            return 2, handler, path_params if path_params is not None else _EMPTY_PARAMS, None  # _FOUND
        if node.allowed:
            return 1, None, path_params if path_params is not None else _EMPTY_PARAMS, node.allow_header  # _METHOD_NOT_ALLOWED
        return 0, None, _EMPTY_PARAMS, None  # _NOT_FOUND


def _segments(path):
    """Split URL path into non-empty segments."""
    return [s for s in path.split("/") if s]
