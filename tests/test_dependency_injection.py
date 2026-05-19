import pytest
from tachyon_api import Tachyon
from tests.helpers import create_client
from tachyon_api.di import injectable, Depends


@injectable
class MockRepository:
    """Simulates a repository that accesses a database."""

    def find_user(self, user_id: int):
        return {"id": user_id, "source": "mock_db", "method": "implicit"}


@injectable
class MockUserService:
    """Simulates a service that depends on the repository."""

    def __init__(self, repo: MockRepository):
        self.repo = repo

    def get_user_data(self, user_id: int):
        return self.repo.find_user(user_id)


@pytest.mark.asyncio
async def test_explicit_dependency_injection():
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/di_explicit/{user_id}")
    def get_user_explicitly(user_id: int, service: MockUserService = Depends()):
        return service.get_user_data(user_id)

    async with create_client(app) as client:
        response = await client.get("/di_explicit/123")

    assert response.status_code == 200
    assert response.json()["source"] == "mock_db"


@pytest.mark.asyncio
async def test_implicit_dependency_injection():
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/di_implicit/{user_id}")
    def get_user_implicitly(user_id: int, service: MockUserService):
        return service.get_user_data(user_id)

    async with create_client(app) as client:
        response = await client.get("/di_implicit/456")

    assert response.status_code == 200
    assert response.json()["id"] == 456
    assert response.json()["source"] == "mock_db"
