# API key delivered via custom HTTP header (e.g. `X-API-Key: ...`).

from typing import Optional

from starlette.requests import Request

from ._api_key_base import _APIKeyBase


class APIKeyHeader(_APIKeyBase):
    """API Key authentication via HTTP header (e.g., 'X-API-Key')."""

    __slots__ = ()

    def _get_raw(self, request: Request) -> Optional[str]:
        return request.headers.get(self.name)
