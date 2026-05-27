# cython: language_level=3, boundscheck=False, wraparound=False
"""LUKEWARM PATH — Cython-compiled Bearer header parser.

Called by HTTPBearer and OAuth2PasswordBearer on every authenticated
request.  Semantics are identical to the pure-Python `_bearer_parser.py`
(case-insensitive `bearer` + 2 whitespace-separated parts, any whitespace
via `str.split()`).  cpdef + typed locals get C dispatch from the
security middlewares; the costly `split()` call stays in CPython's C
implementation either way.

`nogil` + raw `memchr` parsing was on the v1.2.9 plan as "(optional)", but
hand-rolling whitespace scanning would diverge from `str.split()` on
multi-whitespace / non-space whitespace inputs.  The compile-only win is
small but safe; the memchr path is left for v1.3.x once we own a strict
RFC 7235 token parser.
"""


cpdef parse_bearer_header(authorization):
    """Return (scheme, token) for a `Bearer <token>` header, or None if invalid."""
    if not authorization:
        return None
    cdef list parts = authorization.split()
    if len(parts) != 2:
        return None
    cdef str scheme = parts[0]
    if scheme.lower() != "bearer":
        return None
    return scheme, parts[1]
