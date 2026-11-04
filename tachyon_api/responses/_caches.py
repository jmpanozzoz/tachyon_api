"""Bounded immutable headers for small JSON responses."""

from ._constants import _CL_NAME, _CT_JSON, _CT_NAME

# Most small API responses fit here; larger bodies encode their length on demand.
_CL_CACHE = tuple(str(n).encode() for n in range(1024))
_CL_TUPLE_CACHE = tuple((_CL_NAME, value) for value in _CL_CACHE)
_CT_TUPLE = (_CT_NAME, _CT_JSON)
