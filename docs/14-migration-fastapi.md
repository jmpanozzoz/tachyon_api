# 14. Migration from FastAPI

> Guía para migrar de FastAPI a Tachyon

## 🎯 Resumen de Cambios

| Concepto | FastAPI | Tachyon |
|----------|---------|---------|
| App | `FastAPI()` | `Tachyon()` |
| Models | `BaseModel` (pydantic) | `Struct` (msgspec) |
| Router | `APIRouter` | `Router` |
| DI Class | N/A | `@injectable` |
| Response | `JSONResponse` | `TachyonJSONResponse` |
| Files | `UploadFile` | `UploadFile` (mismo) |

---

## 📦 Instalación

```bash
# Remover FastAPI
pip uninstall fastapi pydantic

# Instalar Tachyon
pip install tachyon-api
```

---

## 🔄 Cambios de Import

### Antes (FastAPI):
```python
from fastapi import FastAPI, APIRouter, Depends, Query, Path, Body, Header, Cookie
from fastapi import HTTPException, Request, Response
from fastapi.security import OAuth2PasswordBearer, HTTPBearer
from pydantic import BaseModel
```

### Después (Tachyon):
```python
from tachyon_api import Tachyon, Router, Depends, Query, Path, Body, Header, Cookie
from tachyon_api import HTTPException
from tachyon_api.security import OAuth2PasswordBearer, HTTPBearer
from tachyon_api import Struct

# Request si lo necesitas
from starlette.requests import Request
```

---

## 📝 Modelos: Pydantic → Struct

### Antes (Pydantic):
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

### Después (Struct):
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

### Notas:
- No hay `Config` class
- No hay `Field()` - usa el tipo directamente
- Validators custom van en el Service, no en el modelo

---

## 🔌 Dependency Injection

### Antes (FastAPI):
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

### Después (Tachyon):
```python
from tachyon_api import injectable, Depends

@injectable
class Database:
    def __init__(self):
        self.connection = "connected"

@app.get("/data")
def get_data(db: Database = Depends()):  # Sin función factory
    return {"status": db.connection}
```

### O con callable (similar a FastAPI):
```python
def get_db():
    return Database()

@app.get("/data")
def get_data(db: Database = Depends(get_db)):  # También funciona
    return {"status": db.connection}
```

---

## 🛡️ Security

### Antes (FastAPI):
```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/users/me")
async def get_me(token: str = Depends(oauth2_scheme)):
    return {"token": token}
```

### Después (Tachyon):
```python
from tachyon_api.security import OAuth2PasswordBearer
from tachyon_api import Depends

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/users/me")
async def get_me(token: str = Depends(oauth2_scheme)):
    return {"token": token}
```

**¡Mismo código!** Solo cambia el import.

---

## 🔄 Lifecycle Events

### Antes (FastAPI):
```python
@app.on_event("startup")
async def startup():
    print("Starting...")

@app.on_event("shutdown")
async def shutdown():
    print("Stopping...")
```

### Después (Tachyon) - Igual:
```python
@app.on_event("startup")
async def startup():
    print("Starting...")

@app.on_event("shutdown")
async def shutdown():
    print("Stopping...")
```

### O con lifespan (también igual):
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

### Antes (FastAPI):
```python
from fastapi import BackgroundTasks

@app.post("/send")
def send(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_email)
    return {"status": "queued"}
```

### Después (Tachyon):
```python
from tachyon_api.background import BackgroundTasks

@app.post("/send")
def send(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_email)
    return {"status": "queued"}
```

**¡Solo cambia el import!**

---

## 🌐 WebSockets

### Antes (FastAPI):
```python
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_text()
    await websocket.send_text(f"Echo: {data}")
```

### Después (Tachyon):
```python
@app.websocket("/ws")
async def websocket(websocket):  # No necesita type hint
    await websocket.accept()
    data = await websocket.receive_text()
    await websocket.send_text(f"Echo: {data}")
```

---

## 📁 File Uploads

### Antes (FastAPI):
```python
from fastapi import UploadFile, File

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    contents = await file.read()
    return {"filename": file.filename}
```

### Después (Tachyon):
```python
from tachyon_api import File
from tachyon_api.files import UploadFile

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    contents = await file.read()
    return {"filename": file.filename}
```

---

## 🧪 Testing

### Antes (FastAPI):
```python
from fastapi.testclient import TestClient

def test_api():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
```

### Después (Tachyon):
```python
from tachyon_api.testing import TachyonTestClient

def test_api():
    client = TachyonTestClient(app)
    response = client.get("/")
    assert response.status_code == 200
```

---

## 📋 Checklist de Migración

- [ ] Cambiar imports de `fastapi` a `tachyon_api`
- [ ] Cambiar `BaseModel` a `Struct`
- [ ] Remover `Field()` y `Config` de modelos
- [ ] Agregar `@injectable` a clases de DI
- [ ] Cambiar `FastAPI()` a `Tachyon()`
- [ ] Cambiar `APIRouter` a `Router`
- [ ] Actualizar imports de security
- [ ] Cambiar TestClient
- [ ] Mover validaciones custom a Services
- [ ] Ejecutar tests

---

## ⚡ Performance Gains

Después de migrar, espera:
- **2-5x** mejor serialización JSON
- **30-50%** menos memoria en modelos
- **Startup más rápido** (menos dependencias)

---

## 🔗 Próximos Pasos

- [Best Practices](./15-best-practices.md)
- [Architecture](./02-architecture.md)
