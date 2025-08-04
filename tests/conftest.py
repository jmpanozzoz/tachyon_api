import pytest
from tachyon_api import Tachyon

@pytest.fixture
def app():
    """
    Fixture that provides a Tachyon application instance for testing.
    """

    tachyon_app = Tachyon()

    @tachyon_app.get("/")
    def home():
        return {"message": "Tachyon is running!"}

    @tachyon_app.get("/get")
    def get_endpoint():
        return {"method": "GET", "message": "GET request successful"}

    @tachyon_app.post("/post")
    def post_endpoint():
        return {"method": "POST", "message": "POST request successful"}

    @tachyon_app.put("/put")
    def put_endpoint():
        return {"method": "PUT", "message": "PUT request successful"}

    @tachyon_app.delete("/delete")
    def delete_endpoint():
        return {"method": "DELETE", "message": "DELETE request successful"}

    yield tachyon_app