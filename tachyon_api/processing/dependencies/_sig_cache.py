# HOT PATH — global cache for `inspect.signature()` results.
#
# `inspect.signature()` is O(N) on the parameter count and walks the function's
# __code__ object.  Every Depends(callable) and every @injectable class that
# gets resolved would trigger one call per request.  Caching by identity makes
# the cost amortise to zero after the first resolution.

import inspect
from typing import Callable, Dict

_SIG_CACHE: Dict[Callable, inspect.Signature] = {}


def get_signature(fn: Callable) -> inspect.Signature:
    """Return cached signature for fn (compute on first call, reuse forever)."""
    sig = _SIG_CACHE.get(fn)
    if sig is None:
        sig = inspect.signature(fn)
        _SIG_CACHE[fn] = sig
    return sig
