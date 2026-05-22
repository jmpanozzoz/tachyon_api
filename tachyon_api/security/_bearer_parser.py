# Lukewarm path — parses `Bearer <token>` from an Authorization header value.
#
# Pure function with no I/O — direct cdef + nogil candidate for v1.3.x
# (memchr-based parsing).

from typing import Optional, Tuple


def parse_bearer_header(authorization: Optional[str]) -> Optional[Tuple[str, str]]:
    """Return (scheme, token) for a `Bearer <token>` header, or None if invalid."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[0], parts[1]
