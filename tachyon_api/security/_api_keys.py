# API-key authentication schemes — header, query, and cookie delivery.
# The base class defines the auto-error flow; each subclass answers a single
# question: where does the raw key live on the request?

from abc import ABC, abstractmethod
from typing import Optional

from starlette.requests import Request

from ..exceptions import HTTPException


class _APIKeyBase(ABC):
    """Base class for API-key schemes — defines the auto-error flow."""

    __slots__ = ("name", "auto_error")

    def __init__(self, name: str, auto_error: bool = True) -> None:
        self.name = name
        self.auto_error = auto_error

    @abstractmethod
    def _get_raw(self, request: Request) -> Optional[str]: ...

    async def __call__(self, request: Request) -> Optional[str]:
        api_key = self._get_raw(request)
        if not api_key:
            if self.auto_error:
                raise HTTPException(status_code=403, detail="Not authenticated")
            return None
        return api_key


class APIKeyHeader(_APIKeyBase):
    """API Key authentication via HTTP header (e.g., 'X-API-Key')."""

    __slots__ = ()

    def _get_raw(self, request: Request) -> Optional[str]:
        return request.headers.get(self.name)


class APIKeyQuery(_APIKeyBase):
    """API Key authentication via query parameter (e.g., '?api_key=...').

    Security warning: keys in query parameters appear in server access logs,
    browser history, and Referer headers. Prefer APIKeyHeader or APIKeyCookie
    for any credential that grants meaningful access.
    """

    __slots__ = ()

    def _get_raw(self, request: Request) -> Optional[str]:
        return request.query_params.get(self.name)


class APIKeyCookie(_APIKeyBase):
    """API Key authentication via cookie."""

    __slots__ = ()

    def _get_raw(self, request: Request) -> Optional[str]:
        return request.cookies.get(self.name)
