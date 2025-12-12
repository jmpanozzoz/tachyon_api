"""
Auth Controller - Authentication endpoints.

Endpoints:
- POST /auth/register - Register new user
- POST /auth/login - Login and get token
- GET /auth/me - Get current user info
"""

from tachyon_api import Router, Depends, Body

from ...shared.dependencies import get_current_user
from .auth_service import AuthService
from .auth_dto import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    AuthStatusResponse,
)


router = Router(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse)
def register(
    data: RegisterRequest = Body(...),
    service: AuthService = Depends(),
):
    """
    Register a new user account.
    
    After registration, use /auth/login to get an access token.
    
    **Request Body:**
    - `email`: User's email address
    - `password`: User's password
    - `full_name`: User's full name
    
    **Demo accounts (already registered):**
    - `demo@example.com` / `demo123`
    - `admin@example.com` / `admin123`
    """
    return service.register(data)


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest = Body(...),
    service: AuthService = Depends(),
):
    """
    Authenticate and receive a JWT access token.
    
    Use the returned token in the Authorization header:
    `Authorization: Bearer <token>`
    
    **Demo credentials:**
    - Email: `demo@example.com`
    - Password: `demo123`
    """
    return service.login(data)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    user: dict = Depends(get_current_user),
    service: AuthService = Depends(),
):
    """
    Get the current authenticated user's information.
    
    Requires a valid JWT token in the Authorization header.
    """
    user_info = service.get_user_by_id(user["user_id"])
    
    if not user_info:
        # This shouldn't happen, but just in case
        return UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            full_name="Unknown",
            role=user.get("role", "user"),
        )
    
    return user_info


@router.get("/status", response_model=AuthStatusResponse)
def check_auth_status(
    user: dict = Depends(get_current_user),
    service: AuthService = Depends(),
):
    """
    Check current authentication status.
    
    Returns whether the user is authenticated and their info.
    """
    user_info = service.get_user_by_id(user["user_id"])
    
    return AuthStatusResponse(
        authenticated=True,
        user=user_info,
    )
