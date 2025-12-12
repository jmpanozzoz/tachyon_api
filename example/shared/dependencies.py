"""
Shared dependencies for KYC Demo API.

These are reusable authentication and authorization dependencies.
"""

from typing import Optional
import jwt

from tachyon_api import Depends, Header
from tachyon_api.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config import settings
from .exceptions import UnauthorizedError, ForbiddenError


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


async def get_current_customer(
    user: dict = Depends(get_current_user),
) -> dict:
    """
    Get the current customer from the authenticated user.
    
    In a real app, this would fetch customer details from the database.
    """
    # Mock: In production, fetch from database
    return {
        "customer_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
    }


async def require_api_key(
    api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> str:
    """
    Validate API key from header.
    
    This is useful for service-to-service authentication
    or for external integrations.
    
    Usage:
        @app.get("/api/data")
        def get_data(api_key: str = Depends(require_api_key)):
            return {"data": "secret"}
    """
    if api_key is None:
        raise ForbiddenError("API key required")
    
    if api_key not in settings.valid_api_keys:
        raise ForbiddenError("Invalid API key")
    
    return api_key


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[dict]:
    """
    Optionally extract user from token.
    
    Returns None if no token provided (instead of raising error).
    Useful for endpoints that work with or without authentication.
    """
    if credentials is None:
        return None
    
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
    except jwt.InvalidTokenError:
        return None
