# OAuth2 password-bearer flow — wraps HTTPBearer with a 401 + WWW-Authenticate
# challenge and exposes `tokenUrl` for OpenAPI documentation.

from typing import Optional

from starlette.requests import Request

from ..exceptions import HTTPException
from ._bearer_parser import parse_bearer_header


class OAuth2PasswordBearer:
    """OAuth2 password-bearer flow — returns raw token; 401 on missing/invalid auth."""

    __slots__ = ("tokenUrl", "auto_error")

    def __init__(self, tokenUrl: str, auto_error: bool = True) -> None:
        self.tokenUrl = tokenUrl
        self.auto_error = auto_error

    async def __call__(self, request: Request) -> Optional[str]:
        parsed = parse_bearer_header(request.headers.get("Authorization"))
        if parsed is None:
            if self.auto_error:
                raise HTTPException(
                    status_code=401,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None
        _, token = parsed
        return token
