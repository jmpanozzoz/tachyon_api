# API key delivered via cookie.

from typing import Optional

from starlette.requests import Request

from ._api_key_base import _APIKeyBase


class APIKeyCookie(_APIKeyBase):
    """API Key authentication via cookie."""

    __slots__ = ()

    def _get_raw(self, request: Request) -> Optional[str]:
        return request.cookies.get(self.name)
