"""Starlette benchmark app — bare ASGI, no FastAPI overhead.

Shows the performance ceiling for Starlette-based frameworks.
Same 8 scenarios as app_fastapi.py / app_tachyon.py.
"""

import json
import orjson
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

_CT = b"application/json"


def _json(data) -> Response:
    return Response(orjson.dumps(data), media_type="application/json")


# ── Scenario 1: Hello World ───────────────────────────────────────────────────

async def hello(request: Request) -> Response:
    return _json({"message": "Hello, World!"})


# ── Scenario 2: Path + query params ──────────────────────────────────────────

async def get_item(request: Request) -> Response:
    item_id = int(request.path_params["item_id"])
    q = request.query_params.get("q")
    limit = int(request.query_params.get("limit", "10"))
    return _json({"item_id": item_id, "q": q, "limit": limit})


# ── Scenario 3: Body validation ───────────────────────────────────────────────

async def create_item(request: Request) -> Response:
    body = await request.json()
    return _json({"created": body["name"], "price": body["price"]})


# ── Scenario 4: Nested body ───────────────────────────────────────────────────

async def create_order(request: Request) -> Response:
    body = await request.json()
    total = sum(line["qty"] for line in body["lines"])
    return _json({"customer": body["customer"], "total_items": total})


# ── Scenario 5: Response model serialisation ─────────────────────────────────

async def get_user(request: Request) -> Response:
    uid = int(request.path_params["user_id"])
    return _json({"id": uid, "username": f"user_{uid}", "email": f"user_{uid}@example.com"})


# ── Scenario 6: Header param + auth ──────────────────────────────────────────

async def auth(request: Request) -> Response:
    key = request.headers.get("x-api-key", "")
    if key != "secret":
        return Response(orjson.dumps({"detail": "Forbidden"}),
                        status_code=403, media_type="application/json")
    return _json({"authenticated": True})


# ── Scenario 7: "Dependency injection" (manual) ──────────────────────────────

class _DB:
    def query(self, uid: int):
        return {"id": uid, "source": "db"}

_db = _DB()

async def get_profile(request: Request) -> Response:
    uid = int(request.path_params["user_id"])
    return _json(_db.query(uid))


# ── Scenario 8: Multiple query params ────────────────────────────────────────

async def search(request: Request) -> Response:
    q = request.query_params.get("q", "")
    page = int(request.query_params.get("page", "1"))
    size = int(request.query_params.get("size", "20"))
    active = request.query_params.get("active", "true").lower() == "true"
    return _json({"q": q, "tags": [], "page": page, "size": size, "active": active})


app = Starlette(routes=[
    Route("/hello",                   hello),
    Route("/items/{item_id:int}",     get_item),
    Route("/items",                   create_item,  methods=["POST"]),
    Route("/orders",                  create_order, methods=["POST"]),
    Route("/users/{user_id:int}",     get_user),
    Route("/auth",                    auth),
    Route("/users/{user_id:int}/profile", get_profile),
    Route("/search",                  search),
])
