# cython: language_level=3
"""
Cython-compiled radix trie router.

cdef class _Node: C struct fields — static/param_child/handlers are direct field
reads rather than Python dict-based attribute lookups.
"""

_NOT_FOUND          = 0
_METHOD_NOT_ALLOWED = 1
_FOUND              = 2


cdef class _Node:
    """One trie node. cdef public fields give C-level field access."""

    cdef public dict   static
    cdef public object param_child
    cdef public object param_name
    cdef public dict   handlers
    cdef public object allowed

    def __init__(self):
        self.static      = {}
        self.param_child = None
        self.param_name  = None
        self.handlers    = {}
        self.allowed     = set()


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

    def match(self, path, method):
        """
        Match path + method in O(k).
        Returns (status, handler, path_params, allowed_methods).
        """
        cdef _Node node = self._root
        cdef dict path_params = {}

        for seg in _segments(path):
            existing = node.static.get(seg)
            if existing is not None:
                node = <_Node>existing
            elif node.param_child is not None:
                path_params[(<_Node>node.param_child).param_name] = seg
                node = <_Node>node.param_child
            else:
                return 0, None, {}, None  # _NOT_FOUND

        handler = node.handlers.get(method.upper())
        if handler is not None:
            return 2, handler, path_params, None  # _FOUND
        if node.allowed:
            return 1, None, path_params, node.allowed  # _METHOD_NOT_ALLOWED
        return 0, None, {}, None  # _NOT_FOUND


def _segments(path):
    """Split URL path into non-empty segments."""
    return [s for s in path.split("/") if s]
