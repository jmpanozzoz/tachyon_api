# 14. Migration from FastAPI

> Guide for migrating from FastAPI to Tachyon

## 🎯 Summary of Changes

| Concept | FastAPI | Tachyon |
|----------|---------|---------|
| App | `FastAPI()` | `Tachyon()` |
| Models | `BaseModel` (pydantic) | `Struct` (msgspec) |
| Router | `APIRouter` | `Router` |
| DI Class | N/A | `@injectable` |
| Response | `JSONResponse` | `TachyonJSONResponse` |
| Files | `UploadFile` | `UploadFile` (same) |

---

## 📦 Installation

```bash
# Remove FastAPI
pip uninstall fastapi pydantic

# Install Tachyon
pip install tachyon-api

# Optional: Cython extensions for ~11% extra speed
# pip install tachyon-api[fast]
# python setup.py build_ext --inplace
```

---

## 🔄 Import Changes

### Before (FastAPI):
```python
from fastapi import FastAPI, APIRouter, Depends, Query, Path, Body, Header, Cookie
from fastapi import HTTPException, Request, Response
from fastapi.security import OAuth2PasswordBearer, HTTPBearer
from pydantic import BaseModel
```

### After (Tachyon):
```python
from tachyon_api import Tachyon, Router, Depends, Query, Path, Body, Header, Cookie
from tachyon_api import HTTPException
from tachyon_api.security import OAuth2PasswordBearer, HTTPBearer
from tachyon_api import Struct

# Request if needed
from starlette.requests import Request
```

---

## 📝 Models: Pydantic → Struct

### Before (Pydantic):
```python
from pydantic import BaseModel, Field
from typing import Optional, List

class User(BaseModel):
    name: str
    email: str
    age: int = 18
    tags: List[str] = []
    bio: Optional[str] = None

    class Config:
        extra = "forbid"
```

### After (Struct):
```python
from tachyon_api import Struct
from typing import Optional, List

class User(Struct):
    name: str
    email: str
    age: int = 18
    tags: List[str] = []
    bio: Optional[str] = None
```

### Notes:
- No `Config` class
- No `Field()` — use type annotations directly
- Custom validators belong in the Service layer, not in the model

---

## 🔌 Dependency Injection

### Before (FastAPI):
```python
class Database:
    def __init__(self):
        self.connection = "connected"

def get_db():
    return Database()

@app.get("/data")
def get_data(db: Database = Depends(get_db)):
    return {"status": db.connection}
```

### After (Tachyon) — implicit singleton:
```python
from tachyon_api import injectable, Depends

@injectable
class Database:
    def __init__(self):
        self.connection = "connected"

@app.get("/data")
def get_data(db: Database = Depends()):  # No factory function needed
    return {"status": db.connection}
```

### Or with callable (FastAPI-compatible):
```python
def get_db():
    return Database()

@app.get("/data")
def get_data(db: Database = Depends(get_db)):  # Also works
    return {"status": db.connection}
```

### Key difference
`@injectable` creates an app-scoped singleton (created once, reused across all requests).
FastAPI's `Depends(get_db)` creates a new instance per request unless you add `@lru_cache`.
Tachyon's approach is more efficient for stateless services.

---

## ⚠️ Behavioral Differences vs FastAPI

### Routing
Tachyon uses a radix trie (O(k)) instead of FastAPI's regex-based O(N) routing.
- Trailing slashes are treated as equivalent: `/users` and `/users/` both match the same route.
- No automatic redirect for trailing slash mismatches.

### Middleware stack
Tachyon skips FastAPI/Starlette's automatic `ServerErrorMiddleware` and `ExceptionMiddleware`
for HTTP requests. Exception handling is done per-handler (more efficient). Your custom
middlewares still run. This is transparent unless you relied on Starlette's internal
exception middleware to catch errors from your own middleware.

### `scope["app"]`
Tachyon sets `scope["app"] = self` where `self` is a `Tachyon` instance, not a `Starlette`
instance. Third-party middleware doing `isinstance(scope["app"], Starlette)` will return False.
Most middleware only uses `scope["app"]` for URL generation and is unaffected.

### Response types
`TachyonJSONResponse` is a `JSONResponse` subclass but bypasses Starlette's `Response.__init__`
for performance. It is still compatible with all middleware that checks `isinstance(r, JSONResponse)`.

---

## 🛡️ Security

### Before (FastAPI):
```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/users/me")
async def get_me(token: str = Depends(oauth2_scheme)):
    return {"token": token}
```

### After (Tachyon):
```python
from tachyon_api.security import OAuth2PasswordBearer
from tachyon_api import Depends

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/users/me")
async def get_me(token: str = Depends(oauth2_scheme)):
    return {"token": token}
```

**Only the import changes.**

---

## 🔄 Lifecycle Events

Identical API:

```python
# Both decorators and lifespan context managers work
@app.on_event("startup")
async def startup():
    print("Starting...")

@app.on_event("shutdown")
async def shutdown():
    print("Stopping...")
```

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    print("Starting...")
    yield
    print("Stopping...")

app = Tachyon(lifespan=lifespan)
```

---

## ⚡ Background Tasks

```python
# Before
from fastapi import BackgroundTasks

# After — only the import changes
from tachyon_api.background import BackgroundTasks

@app.post("/send")
def send(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_email)
    return {"status": "queued"}
```

---

## 🌐 WebSockets

```python
# Before (FastAPI)
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket(websocket: WebSocket):
    await websocket.accept()
    ...

# After (Tachyon) — no type hint needed
@app.websocket("/ws")
async def websocket(websocket):
    await websocket.accept()
    ...
```

---

## 📁 File Uploads

```python
# Before
from fastapi import UploadFile, File

# After — minor import change
from tachyon_api import File
from tachyon_api.files import UploadFile

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    contents = await file.read()
    return {"filename": file.filename}
```

---

## 🧪 Testing

```python
# Before
from fastapi.testclient import TestClient

def test_api():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200

# After
from tachyon_api.testing import TachyonTestClient

def test_api():
    client = TachyonTestClient(app)
    response = client.get("/")
    assert response.status_code == 200
```

For async tests, use `httpx.AsyncClient` with `ASGITransport`:
```python
import pytest
import httpx

@pytest.mark.asyncio
async def test_async():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        r = await client.get("/")
    assert r.status_code == 200
```

---

## 📋 Migration Checklist

- [ ] Change imports from `fastapi` to `tachyon_api`
- [ ] Change `BaseModel` to `Struct`
- [ ] Remove `Field()` and `Config` from models
- [ ] Add `@injectable` to DI classes
- [ ] Change `FastAPI()` to `Tachyon()`
- [ ] Change `APIRouter` to `Router`
- [ ] Update security imports
- [ ] Change TestClient to TachyonTestClient
- [ ] Move custom validators to Services
- [ ] Run tests

---

## ⚡ Performance After Migration

Typical results after migrating from FastAPI:
- **5.61x** higher throughput (benchmarked with 100 concurrent connections)
- **~2ms** average latency vs ~14ms in FastAPI
- Serialization via msgspec (C extension) vs Pydantic v2

For maximum performance in production:
```bash
pip install tachyon-api[fast]                          # Cython extensions
python setup.py build_ext --inplace                    # compile
uvicorn app:app --loop uvloop --http httptools          # fast server config
```

---

## 🔗 Next Steps

- [Best Practices](./15-best-practices.md)
- [Architecture](./02-architecture.md)
- [Request Lifecycle](./13-request-lifecycle.md)
