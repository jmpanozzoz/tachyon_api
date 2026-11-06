"""
Auth DTOs - Data Transfer Objects for authentication.
"""

from tachyon_api import Struct
from typing import Annotated
from msgspec import Meta

Email = Annotated[str, Meta(min_length=3, max_length=254)]


class LoginRequest(Struct):
    """Request body for login."""
    
    email: Email
    password: Annotated[str, Meta(min_length=1, max_length=128)]


class RegisterRequest(Struct):
    """Request body for user registration."""
    
    email: Email
    password: Annotated[str, Meta(min_length=10, max_length=128)]
    full_name: Annotated[str, Meta(min_length=1, max_length=120)]


class TokenResponse(Struct):
    """Response containing JWT token."""
    
    access_token: str
    expires_in: int  # seconds
    token_type: str = "bearer"


class UserResponse(Struct):
    """Public user information."""
    
    user_id: str
    email: str
    full_name: str
    role: str = "user"
    is_verified: bool = False
