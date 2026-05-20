"""Shared test models and injectable classes used across multiple test files."""

from tachyon_api.models import Struct
from tachyon_api.di import injectable


@injectable
class MockRepository:
    def find_user(self, user_id: int):
        return {"id": user_id, "source": "mock_db", "method": "implicit"}


@injectable
class MockUserService:
    def __init__(self, repo: MockRepository):
        self.repo = repo

    def get_user_data(self, user_id: int):
        return self.repo.find_user(user_id)


class Item(Struct):
    name: str
    price: float
