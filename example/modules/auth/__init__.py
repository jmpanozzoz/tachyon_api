"""
Auth Module - Authentication and authorization.

Features:
- User registration
- Login (returns JWT)
- Token validation
"""

from .auth_controller import router

__all__ = ["router"]
