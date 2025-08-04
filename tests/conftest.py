import pytest
from tachyon_api import Tachyon
from tachyon_api.params import Body, Query, Path
from tachyon_api.models import Struct
from tachyon_api.di import injectable, Depends


@injectable
class MockRepository:
    """Simula un repositorio que accede a una base de datos."""

    def find_user(self, user_id: int):
        return {"id": user_id, "source": "mock_db", "method": "implicit"}


@injectable
class MockUserService:
    """Simula un servicio que depende del repositorio."""

    def __init__(self, repo: MockRepository):
        self.repo = repo

    def get_user_data(self, user_id: int):
        return self.repo.find_user(user_id)


class Item(Struct):
    """Test model for OpenAPI generation"""

    name: str
    price: float


@pytest.fixture
def app():
    """
    Create a test Tachyon application with sample routes for testing.

    This fixture provides a basic app with routes that exercise different
    parameter types (path params, body params) to test OpenAPI generation.
    """

    tachyon_app = Tachyon()

    @tachyon_app.get("/")
    def home():
        return {"message": "Tachyon is running!"}

    @tachyon_app.get("/get")
    def get_endpoint():
        return {"method": "GET", "message": "GET request successful"}

    @tachyon_app.get("/search")
    def search_items(
        name: str = Query(...),  # Required query parameter
        limit: int = Query(10),
        is_active: bool = Query(False),
    ):
        return {"name": name, "limit": limit, "active": is_active}

    @tachyon_app.get("/items/{item_id}")
    def get_item(item_id: int = Path()):
        return {"item_id_received": item_id, "type": "int"}

    @tachyon_app.post("/post")
    def post_endpoint():
        return {"method": "POST", "message": "POST request successful"}

    @tachyon_app.post("/items")
    def create_item(item: Item = Body()):
        """Create a new item"""
        return {
            "message": "Item created",
            "item_name": item.name,
            "item_price": item.price,
        }

    @tachyon_app.put("/put")
    def put_endpoint():
        return {"method": "PUT", "message": "PUT request successful"}

    @tachyon_app.delete("/delete")
    def delete_endpoint():
        return {"method": "DELETE", "message": "DELETE request successful"}

    @tachyon_app.get("/di_explicit/{user_id}")
    def get_user_explicitly(user_id: int, service: MockUserService = Depends()):
        return service.get_user_data(user_id)

    @tachyon_app.get("/di_implicit/{user_id}")
    def get_user_implicitly(user_id: int, service: MockUserService):
        return service.get_user_data(user_id)

    yield tachyon_app
