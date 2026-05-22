# HOT PATH — single source of truth for "param missing, decide default vs error."
# Consumed by 6 of the 7 user-input extractors.

from ..compiler import ParamDescriptor
from ...responses import validation_error_response
from ._base import ExtractorResult


def missing(descriptor: ParamDescriptor, kind: str, name: str) -> ExtractorResult:
    """Return the descriptor's default, or a 422 if no default is configured."""
    if descriptor.default is not ...:
        return ExtractorResult(descriptor.default, None)
    return ExtractorResult(
        None, validation_error_response(f"Missing required {kind}: {name}")
    )
