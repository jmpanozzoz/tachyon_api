# API key delivered via query parameter (e.g. `?api_key=...`).

from typing import Optional

from starlette.requests import Request

from ._api_key_base import _APIKeyBase


class APIKeyQuery(_APIKeyBase):
    """API Key authentication via query parameter (e.g., '?api_key=...').

    Security warning: keys in query parameters appear in server access logs,
    browser history, and Referer headers. Prefer APIKeyHeader or APIKeyCookie
    for any credential that grants meaningful access.
    """

    __slots__ = ()

    def _get_raw(self, request: Request) -> Optional[str]:
        return request.query_params.get(self.name)
