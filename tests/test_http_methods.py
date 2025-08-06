import pytest
from httpx import AsyncClient, ASGITransport
from tachyon_api import Tachyon

http_test_cases = [
    ("get", "/get", {"method": "GET", "message": "GET request successful"}),
    ("post", "/post", {"method": "POST", "message": "POST request successful"}),
    ("put", "/put", {"method": "PUT", "message": "PUT request successful"}),
    ("delete", "/delete", {"method": "DELETE", "message": "DELETE request successful"}),
]


@pytest.mark.parametrize("http_method, path, expected_payload", http_test_cases)
@pytest.mark.asyncio
async def test_all_http_methods(http_method, path, expected_payload):
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/get")
    def get_endpoint():
        return {"method": "GET", "message": "GET request successful"}

    @app.post("/post")
    def post_endpoint():
        return {"method": "POST", "message": "POST request successful"}

    @app.put("/put")
    def put_endpoint():
        return {"method": "PUT", "message": "PUT request successful"}

    @app.delete("/delete")
    def delete_endpoint():
        return {"method": "DELETE", "message": "DELETE request successful"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await getattr(client, http_method)(path)

    assert response.status_code == 200
    assert response.json() == expected_payload


@pytest.mark.asyncio
async def test_invalid_method():
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/get")
    def get_endpoint():
        return {"method": "GET", "message": "GET request successful"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.patch("/get")
        assert response.status_code == 405
        assert response.text == "Method Not Allowed"
