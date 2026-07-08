"""
Pytest fixtures for KYC Demo API tests.

Demonstrates:
- TachyonTestClient usage
- dependency_overrides for mocking
- Fixture composition
"""

import copy

import pytest
import jwt
from datetime import datetime, timedelta

from tachyon_api.testing import TachyonTestClient

from example.app import app
from example.config import settings
from example.modules.auth import auth_service
from example.modules.customers import customers_repository
from example.modules.verification import verification_repository

_initial_users = copy.deepcopy(auth_service._users_db)


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
def clean_state():
    """
    Reset dependency overrides and in-memory stores after each test.

    The demo repositories keep module-global dicts; without this reset a
    verification created in one test leaks into the next (e.g. an in-progress
    "standard" verification being returned to a test requesting "enhanced").
    """
    yield
    app.dependency_overrides.clear()
    customers_repository._customers_db.clear()
    verification_repository._verifications_db.clear()
    auth_service._users_db.clear()
    auth_service._users_db.update(copy.deepcopy(_initial_users))
