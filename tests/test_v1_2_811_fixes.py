"""Regression tests for the v1.2.811 framework fixes.

Two bugs surfaced while modernizing the example in v1.2.81:
  1. `Body(List[Struct])` failed at runtime because `compile_endpoint` only
     built a msgspec decoder for direct Struct subclasses.
  2. `@app.exception_handler(HTTPException-subclass)` was never invoked because
     `ExceptionTable.dispatch` short-circuited to the default response.
"""

from typing import List, Optional

import pytest
from starlette.responses import JSONResponse

from tachyon_api import Body, HTTPException, Struct, Tachyon
from tests.helpers import create_client


# ── Fix #1: Body(List[Struct]) decodes at runtime ─────────────────────────────


class Item(Struct):
    name: str
    qty: int


@pytest.mark.asyncio
async def test_body_list_of_structs_decodes():
    """`Body(List[ItemStruct])` should accept a JSON array and decode it."""
    app = Tachyon()

    @app.post("/items")
    def create_items(items: List[Item] = Body(...)):
        return {"count": len(items), "names": [it.name for it in items]}

    async with create_client(app) as client:
        response = await client.post(
            "/items",
            json=[{"name": "a", "qty": 1}, {"name": "b", "qty": 2}],
        )

    assert response.status_code == 200
    assert response.json() == {"count": 2, "names": ["a", "b"]}


@pytest.mark.asyncio
async def test_body_list_of_structs_validation_error():
    """Invalid array item should still produce a 422 via msgspec validation."""
    app = Tachyon()

    @app.post("/items")
    def create_items(items: List[Item] = Body(...)):
        return {"ok": True}

    async with create_client(app) as client:
        # `qty` is missing on the second item
        response = await client.post(
            "/items",
            json=[{"name": "a", "qty": 1}, {"name": "b"}],
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_body_optional_struct_decodes():
    """`Body(Optional[Struct])` is also supported by msgspec."""
    app = Tachyon()

    @app.post("/maybe")
    def maybe(item: Optional[Item] = Body(...)):
        return {"received_null": item is None, "name": item.name if item else None}

    async with create_client(app) as client:
        response = await client.post("/maybe", json={"name": "a", "qty": 1})
        assert response.status_code == 200
        assert response.json() == {"received_null": False, "name": "a"}


# ── Fix #2: @app.exception_handler(HTTPException subclass) fires ──────────────


class _DomainError(HTTPException):
    """Domain-specific subclass of HTTPException."""

    def __init__(self, detail: str):
        super().__init__(status_code=418, detail=detail)
        self.error_code = "TEAPOT"


@pytest.mark.asyncio
async def test_exception_handler_subclass_of_http_exception():
    """A handler registered for an HTTPException subclass must be invoked."""
    app = Tachyon()

    @app.exception_handler(_DomainError)
    async def handle_domain_error(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "code": exc.error_code, "msg": exc.detail},
        )

    @app.get("/teapot")
    def raise_teapot():
        raise _DomainError("Short and stout")

    async with create_client(app) as client:
        response = await client.get("/teapot")

    assert response.status_code == 418
    assert response.json() == {
        "success": False,
        "code": "TEAPOT",
        "msg": "Short and stout",
    }


@pytest.mark.asyncio
async def test_plain_http_exception_still_returns_default_body():
    """When no subclass handler matches, plain HTTPException keeps its default body."""
    app = Tachyon()

    @app.get("/notfound")
    def raise_404():
        raise HTTPException(status_code=404, detail="missing")

    async with create_client(app) as client:
        response = await client.get("/notfound")

    assert response.status_code == 404
    assert response.json() == {"detail": "missing"}


@pytest.mark.asyncio
async def test_http_exception_explicit_handler_still_wins_over_default():
    """A handler explicitly registered for HTTPException itself runs first."""
    app = Tachyon()

    @app.exception_handler(HTTPException)
    async def http_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code, content={"caught": exc.detail}
        )

    @app.get("/explicit")
    def raise_400():
        raise HTTPException(status_code=400, detail="bad")

    async with create_client(app) as client:
        response = await client.get("/explicit")

    assert response.status_code == 400
    assert response.json() == {"caught": "bad"}
