import pytest
from tachyon_api import Tachyon
from tachyon_api.params import Path

from tests.shared import MockRepository, MockUserService, Item  # noqa: F401


@pytest.fixture
def app():
    """Minimal app fixture — only endpoints needed by test_path_params.py."""
    tachyon_app = Tachyon()

    @tachyon_app.get("/items/{item_id}")
    def get_item(item_id: int = Path()):
        return {"item_id_received": item_id, "type": "int"}

    yield tachyon_app
