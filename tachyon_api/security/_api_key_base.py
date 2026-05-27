# Abstract base for all API-key authentication schemes.
# Subclasses implement `_get_raw(request)` to extract from header, query, or cookie.

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
