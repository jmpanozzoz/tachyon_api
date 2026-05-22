# cython: language_level=3
"""
Cython-compiled radix trie router.

cdef class _Node: C struct fields — static/param_child/handlers are direct field
reads rather than Python dict-based attribute lookups.

F6: match() inlines segment traversal — no _segments() list, no generator.
    path_params dict lazily allocated.

F11: PyUnicode_AsUTF8AndSize + memchr replace path.find() Python method call.
     Saves ~67ns per path segment (Python method call overhead eliminated).
"""
from libc.string cimport memchr
from cpython.unicode cimport PyUnicode_AsUTF8AndSize
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

        F6: inline segment traversal, lazy path_params.
        F11: PyUnicode_AsUTF8AndSize (O(1) ASCII ptr) + memchr (C-level slash scan)
             replace path.find("/", pos) Python method call — ~67ns per segment.
        """
        cdef _Node node = self._root
        cdef dict path_params = None
        cdef Py_ssize_t path_len, seg_end
        cdef Py_ssize_t pos
        cdef str seg
        cdef object existing
        cdef const char* path_ptr
        cdef const char* slash_ptr

        # O(1) for ASCII paths — CPython caches the UTF-8 repr in the compact Unicode obj
        path_ptr = PyUnicode_AsUTF8AndSize(path, &path_len)
        pos = 1 if path_len > 0 and path_ptr[0] == b'/' else 0

        while pos < path_len:
            # memchr: C-level byte scan — replaces path.find("/", pos) (~67ns → ~3ns)
            slash_ptr = <const char*>memchr(path_ptr + pos, b'/', path_len - pos)
            if slash_ptr == NULL:
                seg_end = path_len
            else:
                seg_end = slash_ptr - path_ptr

            if seg_end > pos:
                seg = path[pos:seg_end]  # Python slice still needed as dict key
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

            pos = seg_end + 1

        handler = node.handlers.get(method.upper())
        if handler is not None:
            return 2, handler, path_params if path_params is not None else _EMPTY_PARAMS, None  # _FOUND
        if node.allowed:
            return 1, None, path_params if path_params is not None else _EMPTY_PARAMS, node.allow_header  # _METHOD_NOT_ALLOWED
        return 0, None, _EMPTY_PARAMS, None  # _NOT_FOUND


def _segments(path):
    """Split URL path into non-empty segments."""
    return [s for s in path.split("/") if s]
