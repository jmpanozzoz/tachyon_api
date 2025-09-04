import pytest
from httpx import AsyncClient, ASGITransport

from tachyon_api import Tachyon, Query


@pytest.mark.asyncio
async def test_openapi_includes_422_and_500_error_responses():
    app = Tachyon()

    @app.get("/items")
    def items(q: str = Query(...)):
        return {"q": q}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        schema = (await client.get("/openapi.json")).json()

    op = schema["paths"]["/items"]["get"]

    assert "422" in op["responses"], "422 response must be present"
    r422 = op["responses"]["422"]["content"]["application/json"]["schema"]
    assert r422["$ref"].endswith(
        "#/components/schemas/ValidationErrorResponse".split("#/", 1)[1]
    ) or r422["$ref"].endswith("#/components/schemas/ValidationErrorResponse")

    assert "500" in op["responses"], "500 response must be present"
    r500 = op["responses"]["500"]["content"]["application/json"]["schema"]
    assert r500["$ref"].endswith(
        "#/components/schemas/ResponseValidationError".split("#/", 1)[1]
    ) or r500["$ref"].endswith("#/components/schemas/ResponseValidationError")

    # Components must include the referenced schemas
    comps = schema["components"]["schemas"]
    assert "ValidationErrorResponse" in comps
    assert "ResponseValidationError" in comps
