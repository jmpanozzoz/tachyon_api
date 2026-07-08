"""
Shared dependencies for KYC Demo API.

These are reusable authentication and authorization dependencies.
"""

from typing import Optional
import jwt

from tachyon_api import Depends
from tachyon_api.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config import settings
from .exceptions import UnauthorizedError


# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """
    Extract and validate the current user from JWT token.

    This dependency:
    1. Extracts the Bearer token from Authorization header
    2. Decodes and validates the JWT
    3. Returns the user payload

    Usage:
        @app.get("/protected")
        def protected(user: dict = Depends(get_current_user)):
            return {"user": user}
    """
    if credentials is None:
        raise UnauthorizedError("Missing authentication token")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", "user"),
        }
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")
