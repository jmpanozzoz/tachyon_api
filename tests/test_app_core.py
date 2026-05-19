import pytest
from tachyon_api import Tachyon
from tests.helpers import create_client


@pytest.mark.asyncio
async def test_home_endpoint_returns_200_and_correct_payload():
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/")
    def home():
        return {"message": "Tachyon is running!"}

    async with create_client(app) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Tachyon is running!"}
