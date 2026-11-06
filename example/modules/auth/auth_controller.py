"""Authentication endpoints; no seeded production accounts."""
from tachyon_api import Router, Depends, Body
from ...shared.dependencies import get_current_user
from .auth_service import AuthService
from .auth_dto import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = Router(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse)
async def register(data: RegisterRequest = Body(...), service: AuthService = Depends()):
    return await service.register(data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest = Body(...), service: AuthService = Depends()):
    return await service.login(data)


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    return UserResponse(**user)
