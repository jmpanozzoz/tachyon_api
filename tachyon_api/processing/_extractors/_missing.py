# HOT PATH — single source of truth for "param missing, decide default vs error."
# Consumed by 6 of the 7 user-input extractors.

from ..compiler import ParamDescriptor
from ...responses import validation_error_response


def missing(descriptor: ParamDescriptor, kind: str, name: str):
    """Return `(default, None)` if a default is set, otherwise `(None, 422-response)`.

    Returns a plain 2-tuple for performance (NamedTuple construction has
    significant overhead at request-rate frequencies).
    """
    if descriptor.default is not ...:
        return (descriptor.default, None)
    return (None, validation_error_response(f"Missing required {kind}: {name}"))
