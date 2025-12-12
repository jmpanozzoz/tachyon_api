"""
Auth DTOs - Data Transfer Objects for authentication.
"""

from typing import Optional
from tachyon_api import Struct


class LoginRequest(Struct):
    """Request body for login."""
    
    email: str
    password: str


class RegisterRequest(Struct):
    """Request body for user registration."""
    
    email: str
    password: str
    full_name: str


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


class AuthStatusResponse(Struct):
    """Current authentication status."""
    
    authenticated: bool
    user: Optional[UserResponse] = None
