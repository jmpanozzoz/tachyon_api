import pytest
from typing import Optional, List
from tests.helpers import create_client

from tachyon_api import Tachyon, Query, Path


@pytest.mark.asyncio
async def test_query_list_of_optional_items_runtime():
    app = Tachyon()

    @app.get("/q")
    def get_q(items: List[Optional[int]] = Query(...)):
        return {"items": items}

    async with create_client(app) as client:
        # mix of values: number, empty, number, null keyword, repeated param
        resp = await client.get("/q?items=1,,3,null&items=5&items=")
        assert resp.status_code == 200
        assert resp.json() == {"items": [1, None, 3, None, 5, None]}

        # invalid value should yield 422
        bad = await client.get("/q?items=1,x,3")
        assert bad.status_code == 422
        assert "Invalid value for integer conversion" in bad.text


@pytest.mark.asyncio
async def test_path_list_of_optional_items_runtime():
    app = Tachyon()

    @app.get("/p/{ids}")
    def get_p(ids: List[Optional[int]] = Path()):
        return {"ids": ids}

    async with create_client(app) as client:
        resp = await client.get("/p/1,,3,null,5,")
        assert resp.status_code == 200
        assert resp.json() == {"ids": [1, None, 3, None, 5, None]}

        bad = await client.get("/p/1,x,3")
        assert bad.status_code == 404
