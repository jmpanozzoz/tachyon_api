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
    """
    HTTP Bearer token authentication scheme.

    Extracts Bearer token from the Authorization header.

    Args:
        auto_error: If True (default), raises HTTPException on missing/invalid token.
                   If False, returns None instead.

    Example:
        security = HTTPBearer()

        @app.get("/protected")
        def protected(credentials: HTTPAuthorizationCredentials = Depends(security)):
            return {"token": credentials.credentials}
    """

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
    """
    HTTP Basic authentication scheme.

    Extracts and decodes username/password from the Authorization header.

    Args:
        auto_error: If True (default), raises HTTPException on missing/invalid credentials.
                   If False, returns None instead.
        realm: The realm name to include in WWW-Authenticate header.

    Example:
        security = HTTPBasic()

        @app.get("/admin")
        def admin(credentials: HTTPBasicCredentials = Depends(security)):
            if credentials.username == "admin" and credentials.password == "secret":
                return {"message": "Welcome, admin!"}
            raise HTTPException(status_code=401, detail="Invalid credentials")
    """

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


class APIKeyHeader:
    """
    API Key authentication via HTTP header.

    Args:
        name: The header name to look for (e.g., "X-API-Key")
        auto_error: If True (default), raises HTTPException on missing key.

    Example:
        api_key = APIKeyHeader(name="X-API-Key")

        @app.get("/api")
        def api_endpoint(key: str = Depends(api_key)):
            return {"api_key": key}
    """

    def __init__(self, name: str, auto_error: bool = True):
        self.name = name
        self.auto_error = auto_error

    async def __call__(self, request: Request) -> Optional[str]:
        api_key = request.headers.get(self.name)

        if not api_key:
            if self.auto_error:
                raise HTTPException(status_code=403, detail="Not authenticated")
            return None

        return api_key


class APIKeyQuery:
    """
    API Key authentication via query parameter.

    Args:
        name: The query parameter name to look for (e.g., "api_key")
        auto_error: If True (default), raises HTTPException on missing key.

    Example:
        api_key = APIKeyQuery(name="api_key")

        @app.get("/api")
        def api_endpoint(key: str = Depends(api_key)):
            return {"api_key": key}
    """

    def __init__(self, name: str, auto_error: bool = True):
        self.name = name
        self.auto_error = auto_error

    async def __call__(self, request: Request) -> Optional[str]:
        api_key = request.query_params.get(self.name)

        if not api_key:
            if self.auto_error:
                raise HTTPException(status_code=403, detail="Not authenticated")
            return None

        return api_key


class APIKeyCookie:
    """
    API Key authentication via cookie.

    Args:
        name: The cookie name to look for (e.g., "session_token")
        auto_error: If True (default), raises HTTPException on missing key.

    Example:
        api_key = APIKeyCookie(name="session_token")

        @app.get("/api")
        def api_endpoint(key: str = Depends(api_key)):
            return {"api_key": key}
    """

    def __init__(self, name: str, auto_error: bool = True):
        self.name = name
        self.auto_error = auto_error

    async def __call__(self, request: Request) -> Optional[str]:
        api_key = request.cookies.get(self.name)

        if not api_key:
            if self.auto_error:
                raise HTTPException(status_code=403, detail="Not authenticated")
            return None

        return api_key


class OAuth2PasswordBearer:
    """
    OAuth2 Password Bearer token scheme.

    Extracts the token from Authorization header (Bearer scheme).
    Similar to HTTPBearer but returns just the token string and uses 401 status.

    Args:
        tokenUrl: The URL to obtain the token (for OpenAPI documentation).
        auto_error: If True (default), raises HTTPException on missing token.

    Example:
        oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

        @app.get("/users/me")
        def get_current_user(token: str = Depends(oauth2_scheme)):
            # Decode and validate token here
            return {"token": token}
    """

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
