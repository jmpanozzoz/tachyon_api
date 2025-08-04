import pytest
from httpx import AsyncClient, ASGITransport

http_test_cases = [
    ("get", "/get", {"method": "GET", "message": "GET request successful"}),
    ("post", "/post", {"method": "POST", "message": "POST request successful"}),
    ("put", "/put", {"method": "PUT", "message": "PUT request successful"}),
    ("delete", "/delete", {"method": "DELETE", "message": "DELETE request successful"}),
]


@pytest.mark.parametrize("http_method, path, expected_payload", http_test_cases)
@pytest.mark.asyncio
async def test_all_http_methods(app, http_method, path, expected_payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await getattr(client, http_method)(path)

    assert response.status_code == 200
    assert response.json() == expected_payload


@pytest.mark.asyncio
async def test_invalid_method(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.patch("/get")
        assert response.status_code == 405
        assert response.text == "Method Not Allowed"
