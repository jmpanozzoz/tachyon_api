# Lukewarm path — HTTP Basic auth.  Decodes the base64 `username:password`
# blob and raises 401 with the WWW-Authenticate challenge if the realm is set.

import base64
import binascii
from typing import Optional

from starlette.requests import Request

from ..exceptions import HTTPException
from ._basic_credentials import HTTPBasicCredentials


class HTTPBasic:
    """Decodes Basic auth credentials from the Authorization header."""

    __slots__ = ("auto_error", "realm")

    def __init__(self, auto_error: bool = True, realm: Optional[str] = None) -> None:
        self.auto_error = auto_error
        self.realm = realm or "simple"

    async def __call__(self, request: Request) -> Optional[HTTPBasicCredentials]:
        authorization = request.headers.get("Authorization")

        if not authorization:
            return self._reject("Not authenticated")

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "basic":
            return self._reject("Invalid authentication credentials")

        try:
            decoded = base64.b64decode(parts[1]).decode("utf-8")
            split = decoded.split(":", 1)
            if len(split) != 2:
                raise ValueError("Missing colon separator in Basic credentials")
            username, password = split
            return HTTPBasicCredentials(username=username, password=password)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return self._reject("Invalid authentication credentials")

    def _reject(self, detail: str) -> None:
        if self.auto_error:
            raise HTTPException(
                status_code=401,
                detail=detail,
                headers={"WWW-Authenticate": f'Basic realm="{self.realm}"'},
            )
        return None
