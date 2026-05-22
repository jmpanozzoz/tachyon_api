# cython: language_level=3, boundscheck=False, wraparound=False
"""HOT PATH — Cython-compiled missing-param helper.

Sibling of `_missing.py`. Single source of truth for the
"param missing → default vs error" decision, used by every user-input
extractor.
"""

from ...responses import validation_error_response
from ._base import ExtractorResult


def missing(descriptor, kind, name):
    """Return the descriptor's default, or a 422 if no default is configured."""
    if descriptor.default is not ...:
        return ExtractorResult(descriptor.default, None)
    return ExtractorResult(
        None, validation_error_response(f"Missing required {kind}: {name}")
    )
