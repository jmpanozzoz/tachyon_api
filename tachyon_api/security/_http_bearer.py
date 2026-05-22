# Lukewarm path — Bearer token authentication scheme.

from typing import Optional

from starlette.requests import Request

from ..exceptions import HTTPException
from ._bearer_credentials import HTTPAuthorizationCredentials
from ._bearer_parser import parse_bearer_header


class HTTPBearer:
    """Extracts a Bearer token from the Authorization header."""

    __slots__ = ("auto_error",)

    def __init__(self, auto_error: bool = True) -> None:
        self.auto_error = auto_error

    async def __call__(
        self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        parsed = parse_bearer_header(request.headers.get("Authorization"))
        if parsed is None:
            if self.auto_error:
                raise HTTPException(status_code=403, detail="Not authenticated")
            return None
        scheme, credentials = parsed
        return HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)
