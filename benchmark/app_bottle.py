"""Bottle benchmark app — WSGI, run with gunicorn.

Uses orjson for JSON serialisation to isolate framework routing overhead.
Same 8 scenarios as the other apps.
"""

import orjson
from bottle import Bottle, request, response as bottle_response

app = Bottle()


def _json(data, status: int = 200):
    bottle_response.content_type = "application/json"
    bottle_response.status = status
    return orjson.dumps(data)


# ── Scenario 1: Hello World ───────────────────────────────────────────────────

@app.route("/hello")
def hello():
    return _json({"message": "Hello, World!"})


# ── Scenario 2: Path + query params ──────────────────────────────────────────

@app.route("/items/<item_id:int>")
def get_item(item_id: int):
    q = request.query.get("q")
    limit = int(request.query.get("limit", 10))
    return _json({"item_id": item_id, "q": q, "limit": limit})


# ── Scenario 3: Body validation ───────────────────────────────────────────────

@app.route("/items", method="POST")
def create_item():
    body = orjson.loads(request.body.read())
    return _json({"created": body["name"], "price": body["price"]})


# ── Scenario 4: Nested body ───────────────────────────────────────────────────

@app.route("/orders", method="POST")
def create_order():
    body = orjson.loads(request.body.read())
    total = sum(line["qty"] for line in body["lines"])
    return _json({"customer": body["customer"], "total_items": total})


# ── Scenario 5: Response model serialisation ─────────────────────────────────

@app.route("/users/<user_id:int>")
def get_user(user_id: int):
    return _json({"id": user_id,
                  "username": f"user_{user_id}",
                  "email": f"user_{user_id}@example.com"})


# ── Scenario 6: Header param + auth ──────────────────────────────────────────

@app.route("/auth")
def auth():
    key = request.headers.get("X-Api-Key", "")
    if key != "secret":
        return _json({"detail": "Forbidden"}, status=403)
    return _json({"authenticated": True})


# ── Scenario 7: "Dependency injection" (manual) ──────────────────────────────

class _DB:
    def query(self, uid: int):
        return {"id": uid, "source": "db"}

_db = _DB()

@app.route("/users/<user_id:int>/profile")
def get_profile(user_id: int):
    return _json(_db.query(user_id))


# ── Scenario 8: Multiple query params ────────────────────────────────────────

@app.route("/search")
def search():
    q = request.query.get("q", "")
    page = int(request.query.get("page", 1))
    size = int(request.query.get("size", 20))
    active = request.query.get("active", "true").lower() == "true"
    return _json({"q": q, "tags": [], "page": page, "size": size, "active": active})
