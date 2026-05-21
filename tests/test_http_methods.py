import pytest
from tachyon_api import Tachyon
from tests.helpers import create_client

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

    async with create_client(app) as client:
        response = await getattr(client, http_method)(path)

    assert response.status_code == 200
    assert response.json() == expected_payload


@pytest.mark.asyncio
async def test_invalid_method():
    app = Tachyon()

    @app.get("/get")
    def get_endpoint():
        return {"method": "GET", "message": "GET request successful"}

    async with create_client(app) as client:
        response = await client.patch("/get")
        assert response.status_code == 405
        assert response.text == "Method Not Allowed"


@pytest.mark.asyncio
async def test_405_allow_header_single_method():
    """HF-08: Allow header must be present and correct for single-method routes."""
    app = Tachyon()

    @app.get("/items")
    def get_items():
        return []

    async with create_client(app) as client:
        r = await client.post("/items")

    assert r.status_code == 405
    assert r.headers.get("allow") == "GET"
    assert r.headers.get("content-type") == "text/plain; charset=utf-8"


@pytest.mark.asyncio
async def test_405_allow_header_multiple_methods_presorted():
    """HF-08: Allow header must list methods alphabetically."""
    app = Tachyon()

    @app.post("/endpoint")
    def create():
        return {}

    @app.get("/endpoint")
    def read():
        return {}

    @app.delete("/endpoint")
    def delete():
        return {}

    async with create_client(app) as client:
        r = await client.patch("/endpoint")

    assert r.status_code == 405
    assert r.headers.get("allow") == "DELETE, GET, POST"


@pytest.mark.asyncio
async def test_404_body_and_content_type():
    """HF-08: 404 response must have correct body and content-type."""
    app = Tachyon()

    @app.get("/exists")
    def ep():
        return {}

    async with create_client(app) as client:
        r = await client.get("/does-not-exist")

    assert r.status_code == 404
    assert r.text == "Not Found"
    assert "text/plain" in r.headers.get("content-type", "")
