# HOT PATH — uniform result type for every extractor.
# NamedTuple lowers to a C struct under Cython.

from typing import Any, NamedTuple, Optional

from starlette.responses import JSONResponse


class ExtractorResult(NamedTuple):
    """Uniform return shape from every extractor: (value, error)."""

    value: Any
    error: Optional[JSONResponse]


OK_NONE: ExtractorResult = ExtractorResult(None, None)
