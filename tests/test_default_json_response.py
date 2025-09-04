import pytest
import uuid
import datetime
from httpx import AsyncClient, ASGITransport

from tachyon_api import Tachyon
from tachyon_api.models import Struct


class Sample(Struct):
    id: int
    created_at: datetime.date


@pytest.mark.asyncio
async def test_default_response_serializes_datetime_and_uuid_with_orjson():
    app = Tachyon()

    test_uuid = uuid.uuid4()
    test_date = datetime.date.today()

    @app.get("/info")
    def info():
        # Return types that standard JSONResponse can't serialize by default
        return {"uuid": test_uuid, "today": test_date}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/info")

    assert response.status_code == 200
    data = response.json()
    assert data["uuid"] == str(test_uuid)
    assert data["today"] == test_date.isoformat()


@pytest.mark.asyncio
async def test_default_response_handles_struct_directly():
    app = Tachyon()

    @app.get("/struct")
    def get_struct():
        return Sample(id=1, created_at=datetime.date(2020, 1, 2))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/struct")

    assert response.status_code == 200
    data = response.json()
    assert data == {"id": 1, "created_at": "2020-01-02"}
