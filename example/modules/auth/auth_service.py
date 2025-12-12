"""
Auth Service - Authentication business logic.

This service handles:
- User registration
- Login and token generation
- Password hashing (mocked for demo)
"""

from datetime import datetime, timedelta
from typing import Optional
import uuid
import jwt

from tachyon_api import injectable

from ...config import settings
from ...shared.exceptions import UnauthorizedError
from .auth_dto import LoginRequest, RegisterRequest, TokenResponse, UserResponse


# Mock user database
_users_db: dict = {
    "demo@example.com": {
        "user_id": "user_demo_001",
        "email": "demo@example.com",
        "password_hash": "demo123",  # In production: bcrypt hash
        "full_name": "Demo User",
        "role": "user",
        "is_verified": True,
    },
    "admin@example.com": {
        "user_id": "user_admin_001",
        "email": "admin@example.com",
        "password_hash": "admin123",
        "full_name": "Admin User",
        "role": "admin",
        "is_verified": True,
    },
}


@injectable
class AuthService:
    """
    Authentication service.
    
    Handles user registration, login, and token management.
    """
    
    def register(self, data: RegisterRequest) -> UserResponse:
        """
        Register a new user.
        
        In production:
        - Hash password with bcrypt
        - Store in database
        - Send verification email
        """
        # Check if email already exists
        if data.email in _users_db:
            raise UnauthorizedError("Email already registered")
        
        # Create new user
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        
        _users_db[data.email] = {
            "user_id": user_id,
            "email": data.email,
            "password_hash": data.password,  # In production: bcrypt.hash()
            "full_name": data.full_name,
            "role": "user",
            "is_verified": False,
        }
        
        return UserResponse(
            user_id=user_id,
            email=data.email,
            full_name=data.full_name,
            role="user",
            is_verified=False,
        )
    
    def login(self, data: LoginRequest) -> TokenResponse:
        """
        Authenticate user and return JWT token.
        
        In production:
        - Verify password with bcrypt
        - Log login attempt
        - Implement rate limiting
        """
        user = _users_db.get(data.email)
        
        if not user:
            raise UnauthorizedError("Invalid email or password")
        
        # Mock password verification
        if user["password_hash"] != data.password:
            raise UnauthorizedError("Invalid email or password")
        
        # Generate JWT token
        token = self._create_token(user)
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.jwt_expiration_hours * 3600,
        )
    
    def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        """Get user by email address."""
        user = _users_db.get(email)
        
        if not user:
            return None
        
        return UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_verified=user["is_verified"],
        )
    
    def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """Get user by ID."""
        for user in _users_db.values():
            if user["user_id"] == user_id:
                return UserResponse(
                    user_id=user["user_id"],
                    email=user["email"],
                    full_name=user["full_name"],
                    role=user["role"],
                    is_verified=user["is_verified"],
                )
        return None
    
    def _create_token(self, user: dict) -> str:
        """Create a JWT token for the user."""
        expiration = datetime.utcnow() + timedelta(
            hours=settings.jwt_expiration_hours
        )
        
        payload = {
            "sub": user["user_id"],
            "email": user["email"],
            "role": user["role"],
            "exp": expiration,
            "iat": datetime.utcnow(),
        }
        
        return jwt.encode(
            payload,
            settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )
