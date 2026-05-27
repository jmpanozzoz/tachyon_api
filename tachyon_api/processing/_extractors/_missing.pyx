# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled missing-param helper.

Sibling of `_missing.py`. Single source of truth for the
"param missing → default vs error" decision, used by every user-input
extractor.
"""

from ...responses import validation_error_response


def missing(descriptor, kind, name):
    """Return `(default, None)` if a default is set, otherwise `(None, 422-response)`.

    Plain tuple — NamedTuple construction is too costly at request rates.
    """
    if descriptor.default is not ...:
        return (descriptor.default, None)
    return (None, validation_error_response(f"Missing required {kind}: {name}"))
