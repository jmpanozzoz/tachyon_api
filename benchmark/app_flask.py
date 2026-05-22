"""Flask benchmark app — WSGI, run with gunicorn.

Uses orjson for JSON serialisation to isolate framework routing overhead
from JSON library performance.  Same 8 scenarios as the other apps.
"""

import orjson
from flask import Flask, request, Response

app = Flask(__name__)


def _json(data, status: int = 200) -> Response:
    return Response(orjson.dumps(data), status=status, mimetype="application/json")


# ── Scenario 1: Hello World ───────────────────────────────────────────────────

@app.get("/hello")
def hello():
    return _json({"message": "Hello, World!"})


# ── Scenario 2: Path + query params ──────────────────────────────────────────

@app.get("/items/<int:item_id>")
def get_item(item_id: int):
    q = request.args.get("q")
    limit = int(request.args.get("limit", 10))
    return _json({"item_id": item_id, "q": q, "limit": limit})


# ── Scenario 3: Body validation ───────────────────────────────────────────────

@app.post("/items")
def create_item():
    body = request.get_json(force=True)
    return _json({"created": body["name"], "price": body["price"]})


# ── Scenario 4: Nested body ───────────────────────────────────────────────────

@app.post("/orders")
def create_order():
    body = request.get_json(force=True)
    total = sum(line["qty"] for line in body["lines"])
    return _json({"customer": body["customer"], "total_items": total})


# ── Scenario 5: Response model serialisation ─────────────────────────────────

@app.get("/users/<int:user_id>")
def get_user(user_id: int):
    return _json({"id": user_id,
                  "username": f"user_{user_id}",
                  "email": f"user_{user_id}@example.com"})


# ── Scenario 6: Header param + auth ──────────────────────────────────────────

@app.get("/auth")
def auth():
    key = request.headers.get("x-api-key", "")
    if key != "secret":
        return _json({"detail": "Forbidden"}, status=403)
    return _json({"authenticated": True})


# ── Scenario 7: "Dependency injection" (manual) ──────────────────────────────

class _DB:
    def query(self, uid: int):
        return {"id": uid, "source": "db"}

_db = _DB()

@app.get("/users/<int:user_id>/profile")
def get_profile(user_id: int):
    return _json(_db.query(user_id))


# ── Scenario 8: Multiple query params ────────────────────────────────────────

@app.get("/search")
def search():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 20))
    active = request.args.get("active", "true").lower() == "true"
    return _json({"q": q, "tags": [], "page": page, "size": size, "active": active})
