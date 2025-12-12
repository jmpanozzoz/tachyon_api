"""
Project scaffolding templates.
"""


class ProjectTemplates:
    """Templates for `tachyon new` command."""

    APP = '''"""
Main application entry point.
"""

import uvicorn
from tachyon_api import Tachyon
from config import settings

# Initialize app
app = Tachyon()


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/health")
def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
    }


# Import and register routers here
# from modules.users import router as users_router
# app.include_router(users_router)


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
'''

    CONFIG = '''"""
Application configuration.
"""

import os


class Settings:
    """Application settings loaded from environment variables."""
    
    APP_NAME: str = os.getenv("APP_NAME", "Tachyon API")
    VERSION: str = os.getenv("VERSION", "0.1.0")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Database (example)
    # DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")


settings = Settings()
'''

    REQUIREMENTS = """# Tachyon API Framework
tachyon-api>=0.6.0

# Server
uvicorn[standard]>=0.30.0

# Development
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
ruff>=0.4.0
"""

    MODULES_INIT = '''"""
Application modules.

Each module follows clean architecture:
- controller: HTTP endpoints (router)
- service: Business logic
- repository: Data access
- dto: Data transfer objects
"""
'''

    SHARED_INIT = '''"""
Shared utilities and dependencies.
"""

from .exceptions import *
from .dependencies import *
'''

    SHARED_EXCEPTIONS = '''"""
Custom application exceptions.
"""

from tachyon_api import HTTPException


class NotFoundError(HTTPException):
    """Resource not found."""
    
    def __init__(self, resource: str, id: str):
        super().__init__(
            status_code=404,
            detail=f"{resource} with id '{id}' not found"
        )


class UnauthorizedError(HTTPException):
    """Authentication required."""
    
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=401,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class ForbiddenError(HTTPException):
    """Access denied."""
    
    def __init__(self, detail: str = "Access denied"):
        super().__init__(status_code=403, detail=detail)


class BadRequestError(HTTPException):
    """Invalid request."""
    
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)


class ConflictError(HTTPException):
    """Resource conflict (e.g., duplicate)."""
    
    def __init__(self, detail: str):
        super().__init__(status_code=409, detail=detail)
'''

    SHARED_DEPENDENCIES = '''"""
Shared dependencies for dependency injection.
"""

from tachyon_api import Depends
from tachyon_api.security import OAuth2PasswordBearer

# Example: OAuth2 token dependency
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
# 
# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     # Validate token and return user
#     pass
'''

    TESTS_CONFTEST = '''"""
Pytest configuration and fixtures.
"""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def app():
    """Create test application instance."""
    from app import app
    return app


@pytest.fixture
async def client(app):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
'''
