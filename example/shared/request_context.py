"""
Request-scoped context — a fresh instance per HTTP request.

Demonstrates `@injectable(scope="request")`: every request gets its own
RequestContext with a unique correlation_id. Sub-deps that themselves
declare `Depends(RequestContext)` get the SAME instance within one request,
and a NEW instance on the next request.

Use cases:
- Correlation ID for log tracing across services in one request
- Per-request feature flags / experiments
- Carrying parsed auth info across multiple deps without re-decoding
"""

import uuid
from typing import Any, Dict

from tachyon_api import injectable


@injectable(scope="request")
class RequestContext:
    """One instance per HTTP request — shared by all deps that ask for it."""

    def __init__(self) -> None:
        self.correlation_id: str = str(uuid.uuid4())
        self.attributes: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)
