"""Tachyon benchmark app — mirrors app_fastapi.py endpoint-for-endpoint."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import Optional, List
from tachyon_api import Tachyon, Struct, Body, Query, Path, Header
from tachyon_api.exceptions import HTTPException

app = Tachyon()


# --- Models ---

class Item(Struct):
    name: str
    price: float
    in_stock: bool = True


class OrderLine(Struct):
    item_id: int
    qty: int


class Order(Struct):
    customer: str
    lines: List[OrderLine]


class UserOut(Struct):
    id: int
    username: str
    email: str


# --- Scenario 1: Hello World ---

@app.get("/hello")
def hello():
    return {"message": "Hello, World!"}


# --- Scenario 2: Path + query params ---

@app.get("/items/{item_id}")
def get_item(
    item_id: int,
    q: Optional[str] = Query(None),
    limit: int = Query(10),
):
    return {"item_id": item_id, "q": q, "limit": limit}


# --- Scenario 3: Body validation ---

@app.post("/items")
def create_item(item: Item = Body()):
    return {"created": item.name, "price": item.price}


# --- Scenario 4: Nested body ---

@app.post("/orders")
def create_order(order: Order = Body()):
    total = sum(line.qty for line in order.lines)
    return {"customer": order.customer, "total_items": total}


# --- Scenario 5: Response model ---

@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    return UserOut(id=user_id, username=f"user_{user_id}", email=f"user_{user_id}@example.com")


# --- Scenario 6: Header param ---

@app.get("/auth")
def auth(x_api_key: str = Header(...)):
    if x_api_key != "secret":
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"authenticated": True}


# --- Scenario 7: Dependency injection ---

from tachyon_api.di import injectable, Depends

@injectable
class Database:
    def query(self, user_id: int):
        return {"id": user_id, "source": "db"}

@app.get("/users/{user_id}/profile")
def get_profile(user_id: int, db: Database = Depends()):
    return db.query(user_id)


# --- Scenario 8: Multiple query params + list ---

@app.get("/search")
def search(
    q: str = Query(...),
    page: int = Query(1),
    size: int = Query(20),
    active: bool = Query(True),
):
    return {"q": q, "tags": [], "page": page, "size": size, "active": active}
