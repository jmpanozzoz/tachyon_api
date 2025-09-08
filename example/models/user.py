"""
User models for the Tachyon API v0.4.0 Demo
"""

from tachyon_api.schemas.models import Struct


class User(Struct):
    """User model"""

    id: int
    name: str
    email: str


class CreateUserRequest(Struct):
    """Request model for creating a new user"""

    name: str
    email: str
