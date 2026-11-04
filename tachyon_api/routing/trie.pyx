# cython: language_level=3
"""
Path trie router with static priority and wildcard fallback.

Replaces Starlette's O(N × regex) linear route scan. Each static segment is
a dict lookup. Ambiguous branches backtrack when a static path dead-ends.

Path format: /users/{user_id}/profile  (Starlette / FastAPI convention)
"""


from types import MappingProxyType


_NOT_FOUND          = 0
_METHOD_NOT_ALLOWED = 1
_FOUND              = 2

# Immutable empty sentinel — returned for routes with no path params.
# MappingProxyType prevents accidental mutation; safe because nobody writes to path_params.
_EMPTY_PARAMS = MappingProxyType({})


cdef class _Node:
    cdef public dict static
    cdef public object param_child
    cdef public dict param_names
    cdef public dict handlers
    cdef public object allowed
    cdef public str allow_header

    def __init__(self):
        self.static = {}
        self.param_child = None
        self.param_names = {}
        self.handlers = {}
        self.allowed = set()
        self.allow_header = ""


cdef class RadixTrie:
    """
    Register routes at startup; prefer static paths with wildcard fallback.

    Usage:
        trie = RadixTrie()
        trie.add("/users/{id}", "GET", handler)
        status, handler, params, allowed = trie.match("/users/42", "GET")
    """

    cdef public _Node _root

    def __init__(self):
        self._root = _Node()

    # ── Registration ────────────────────────────────────────────────────────

    def add(self, path, method, handler):
        """Register a (path, method) → handler mapping."""
        cdef _Node node = self._root
        names = []
        for seg in _segments(path):
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

    def match(self, str path, str method):
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
        cdef _Node node = self._root
        cdef Py_ssize_t pos = 0
        cdef _Node child
        cdef object wildcard
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



def _segments(path):
    """Split a URL path into non-empty segments."""
    return [s for s in path.split("/") if s]
