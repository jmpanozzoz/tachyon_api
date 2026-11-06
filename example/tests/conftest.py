"""Integration tests use an explicit disposable PostgreSQL database, never SQLite."""
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from sqlalchemy import text

from example.app import create_app
from example.config import Settings
from example.shared.models import Base
from tachyon_api.testing import TachyonTestClient, create_client


@pytest.fixture(scope="session")
def migrated_database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    if not urlsplit(url).path.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must target a disposable database ending in _test")
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DATABASE_URL": url, "ENVIRONMENT": "test"}
    subprocess.run([sys.executable, "-m", "alembic", "-c", "example/alembic.ini", "upgrade", "head"],
                   cwd=root, env=env, check=True, capture_output=True)
    return url


@pytest.fixture
def application(migrated_database):
    return create_app(Settings(environment="test", secret_key="reference-test-key-only-with-32-characters",
        database_url=migrated_database, redis_url=os.getenv("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")))


async def clear(application):
    # The database name guard above is mandatory; these integration tests are serial.
    names = ", ".join('"' + t.name + '"' for t in Base.metadata.sorted_tables)
    async with application.state.engine.begin() as conn:
        await conn.execute(text("TRUNCATE " + names + " CASCADE"))
    try:
        keys = [key async for key in application.state.redis.scan_iter(match="reference:*")]
        if keys:
            await application.state.redis.delete(*keys)
    except Exception:
        pass  # Redis-down behavior is tested explicitly; DB state is still isolated.


@pytest.fixture
def client(application):
    with TachyonTestClient(application) as client:
        client.portal.call(clear, application)
        yield client


@pytest_asyncio.fixture
async def async_client(application):
    async with LifespanManager(application):
        await clear(application)
        async with create_client(application) as client:
            yield client


def register(client, name="alice"):
    data = {"email": name + "@example.com", "password": "synthetic-password", "full_name": name}
    response = client.post("/auth/register", json=data)
    assert response.status_code == 200, response.text
    user = response.json()
    login = client.post("/auth/login", json={"email": data["email"], "password": data["password"]})
    assert login.status_code == 200, login.text
    return user, {"Authorization": "Bearer " + login.json()["access_token"]}


@pytest.fixture
def identity(client):
    return register(client)


@pytest.fixture
def auth_headers(identity):
    return identity[1]


@pytest.fixture
def customer(client, auth_headers):
    result = client.post("/customers/", headers=auth_headers,
        json={"first_name": "Alice", "last_name": "Example", "email": "synthetic@example.com"})
    assert result.status_code == 200, result.text
    return result.json()
