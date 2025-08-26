import pytest
from httpx import AsyncClient, ASGITransport
from typing import Optional, List
import uuid
import datetime

from tachyon_api import Tachyon
from tachyon_api.models import Struct
from tachyon_api.params import Body


class Address(Struct):
    street: str
    zip_code: Optional[str] = None


class UserIn(Struct):
    name: str
    address: Optional[Address] = None
    tags: Optional[List[str]] = None


class UserOut(Struct):
    id: int
    name: str
    tags: List[str]
    uid: uuid.UUID
    created_at: datetime.datetime
    address: Optional[Address] = None


@pytest.mark.asyncio
async def test_openapi_structs_nested_and_optional():
    app = Tachyon()

    @app.post("/users", response_model=UserOut)
    def create_user(user: UserIn = Body()):
        return {
            "id": 1,
            "name": user.name,
            "address": user.address,
            "tags": user.tags or [],
            "uid": uuid.uuid4(),
            "created_at": datetime.datetime.now(),
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        schema = (await client.get("/openapi.json")).json()

    comps = schema["components"]["schemas"]
    assert "Address" in comps
    assert comps["Address"]["type"] == "object"
    assert "street" in comps["Address"]["properties"]
    assert "zip_code" in comps["Address"]["properties"]
    assert comps["Address"]["properties"]["zip_code"]["nullable"] is True
    assert "street" in comps["Address"]["required"]

    assert "UserOut" in comps
    uo = comps["UserOut"]
    assert uo["type"] == "object"
    assert "id" in uo["required"] and "name" in uo["required"]
    assert uo["properties"]["address"]["nullable"] is True
    assert uo["properties"]["address"]["$ref"].endswith("#/components/schemas/Address".split("#/",1)[1]) or uo["properties"]["address"]["$ref"].endswith("#/components/schemas/Address")
    assert uo["properties"]["tags"]["type"] == "array"
    assert uo["properties"]["tags"]["items"]["type"] == "string"
    assert uo["properties"]["uid"]["type"] == "string" and uo["properties"]["uid"]["format"] == "uuid"
    assert uo["properties"]["created_at"]["type"] == "string" and uo["properties"]["created_at"]["format"] == "date-time"

    # Request body must reference UserIn
    op = schema["paths"]["/users"]["post"]
    rb = op["requestBody"]["content"]["application/json"]["schema"]
    assert rb["$ref"].endswith("#/components/schemas/UserIn".split("#/",1)[1]) or rb["$ref"].endswith("#/components/schemas/UserIn")
