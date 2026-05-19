"""
Tachyon Security Module

Provides security schemes for authentication and authorization,
compatible with FastAPI's security utilities.
"""

import base64
from typing import Optional

from starlette.requests import Request

from .exceptions import HTTPException


class HTTPAuthorizationCredentials:
    """
    Credentials extracted from HTTP Authorization header.

    Attributes:
        scheme: The authentication scheme (e.g., "Bearer", "Basic")
        credentials: The credentials value (e.g., the token or encoded credentials)
    """

    def __init__(self, scheme: str, credentials: str):
        self.scheme = scheme
        self.credentials = credentials


class HTTPBasicCredentials:
    """
    Credentials extracted from HTTP Basic authentication.

    Attributes:
        username: The decoded username
        password: The decoded password
    """

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password


class HTTPBearer:
    """Extracts Bearer token from Authorization header. Returns HTTPAuthorizationCredentials."""

    def __init__(self, auto_error: bool = True):
        self.auto_error = auto_error

    async def __call__(
        self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        authorization = request.headers.get("Authorization")

        if not authorization:
            if self.auto_error:
                raise HTTPException(status_code=403, detail="Not authenticated")
            return None

        parts = authorization.split()
        if len(parts) != 2:
            if self.auto_error:
                raise HTTPException(
                    status_code=403, detail="Invalid authorization header"
                )
            return None

        scheme, credentials = parts

        if scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=403, detail="Invalid authentication scheme"
                )
            return None

        return HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)


class HTTPBasic:
    """Decodes Basic auth credentials from Authorization header. Returns HTTPBasicCredentials."""

    def __init__(self, auto_error: bool = True, realm: Optional[str] = None):
        self.auto_error = auto_error
        self.realm = realm or "simple"

    async def __call__(self, request: Request) -> Optional[HTTPBasicCredentials]:
        authorization = request.headers.get("Authorization")

        if not authorization:
            if self.auto_error:
                raise HTTPException(
                    status_code=401,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": f'Basic realm="{self.realm}"'},
                )
            return None

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "basic":
            if self.auto_error:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": f'Basic realm="{self.realm}"'},
                )
            return None

        try:
            decoded = base64.b64decode(parts[1]).decode("utf-8")
            username, password = decoded.split(":", 1)
            return HTTPBasicCredentials(username=username, password=password)
        except Exception:
            if self.auto_error:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": f'Basic realm="{self.realm}"'},
                )
            return None


class _APIKeyBase:
    def __init__(self, name: str, auto_error: bool = True):
        self.name = name
        self.auto_error = auto_error

    def _get_raw(self, request: Request) -> Optional[str]:
        raise NotImplementedError

    async def __call__(self, request: Request) -> Optional[str]:
        api_key = self._get_raw(request)
        if not api_key:
            if self.auto_error:
                raise HTTPException(status_code=403, detail="Not authenticated")
            return None
        return api_key


class APIKeyHeader(_APIKeyBase):
    """API Key authentication via HTTP header (e.g., 'X-API-Key')."""

    def _get_raw(self, request: Request) -> Optional[str]:
        return request.headers.get(self.name)


class APIKeyQuery(_APIKeyBase):
    """API Key authentication via query parameter (e.g., '?api_key=...')."""

    def _get_raw(self, request: Request) -> Optional[str]:
        return request.query_params.get(self.name)


class APIKeyCookie(_APIKeyBase):
    """API Key authentication via cookie."""

    def _get_raw(self, request: Request) -> Optional[str]:
        return request.cookies.get(self.name)


class OAuth2PasswordBearer:
    """Like HTTPBearer but returns raw token string and uses 401 (tokenUrl for OpenAPI docs)."""

    def __init__(self, tokenUrl: str, auto_error: bool = True):
        self.tokenUrl = tokenUrl
        self.auto_error = auto_error

    async def __call__(self, request: Request) -> Optional[str]:
        authorization = request.headers.get("Authorization")

        if not authorization:
            if self.auto_error:
                raise HTTPException(
                    status_code=401,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None

        return parts[1]
