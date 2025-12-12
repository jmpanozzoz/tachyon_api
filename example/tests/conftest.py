"""
Pytest fixtures for KYC Demo API tests.

Demonstrates:
- TachyonTestClient usage
- dependency_overrides for mocking
- Fixture composition
"""

import pytest
import jwt
from datetime import datetime, timedelta

from tachyon_api.testing import TachyonTestClient

from ..app import app
from ..config import settings


@pytest.fixture
def client():
    """
    Create a test client for the KYC API.
    
    This client wraps the app and handles HTTP requests.
    """
    return TachyonTestClient(app)


@pytest.fixture
def auth_token():
    """
    Generate a valid JWT token for testing.
    """
    payload = {
        "sub": "test_user_001",
        "email": "test@example.com",
        "role": "user",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
    }
    
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.fixture
def auth_headers(auth_token):
    """
    Generate authorization headers with JWT token.
    """
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_token():
    """
    Generate a JWT token for admin user.
    """
    payload = {
        "sub": "admin_user_001",
        "email": "admin@example.com",
        "role": "admin",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
    }
    
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.fixture
def admin_headers(admin_token):
    """
    Generate authorization headers for admin.
    """
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(autouse=True)
def clean_overrides():
    """
    Clean dependency overrides after each test.
    """
    yield
    app.dependency_overrides.clear()
