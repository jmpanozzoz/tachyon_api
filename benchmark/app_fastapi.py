"""FastAPI benchmark app — matches tachyon_app.py endpoint-for-endpoint."""

from typing import Optional, List
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


# --- Models ---

class Item(BaseModel):
    name: str
    price: float
    in_stock: bool = True


class OrderLine(BaseModel):
    item_id: int
    qty: int


class Order(BaseModel):
    customer: str
    lines: List[OrderLine]


class UserOut(BaseModel):
    id: int
    username: str
    email: str


# --- Scenario 1: Hello World (bare minimum) ---

@app.get("/hello")
def hello():
    return {"message": "Hello, World!"}


# --- Scenario 2: Path + query params ---

@app.get("/items/{item_id}")
def get_item(item_id: int, q: Optional[str] = None, limit: int = 10):
    return {"item_id": item_id, "q": q, "limit": limit}


# --- Scenario 3: Body validation (POST) ---

@app.post("/items")
def create_item(item: Item):
    return {"created": item.name, "price": item.price}


# --- Scenario 4: Nested body (complex struct) ---

@app.post("/orders")
def create_order(order: Order):
    total = sum(line.qty for line in order.lines)
    return {"customer": order.customer, "total_items": total}


# --- Scenario 5: Response model ---

@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    return {"id": user_id, "username": f"user_{user_id}", "email": f"user_{user_id}@example.com"}


# --- Scenario 6: Header param ---

@app.get("/auth")
def auth(x_api_key: str = Header(...)):
    if x_api_key != "secret":
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"authenticated": True}


# --- Scenario 7: Dependency injection ---

class Database:
    def query(self, user_id: int):
        return {"id": user_id, "source": "db"}

def get_db():
    return Database()

@app.get("/users/{user_id}/profile")
def get_profile(user_id: int, db: Database = Depends(get_db)):
    return db.query(user_id)


# --- Scenario 8: Multiple query params + list ---

@app.get("/search")
def search(
    q: str,
    tags: Optional[List[str]] = None,
    page: int = 1,
    size: int = 20,
    active: bool = True,
):
    return {"q": q, "tags": tags or [], "page": page, "size": size, "active": active}
