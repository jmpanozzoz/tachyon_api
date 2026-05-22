# 11. Testing

> Guía completa de testing para Tachyon

## 🎯 TachyonTestClient

Cliente de test síncrono:

```python
from tachyon_api import Tachyon
from tachyon_api.testing import TachyonTestClient

app = Tachyon()

@app.get("/hello")
def hello():
    return {"message": "Hello!"}

# Test
def test_hello():
    client = TachyonTestClient(app)
    response = client.get("/hello")
    
    assert response.status_code == 200
    assert response.json() == {"message": "Hello!"}
```

---

## 🔄 Async clients

Tachyon expone dos formas equivalentes de testear async — ambas montan
`httpx.AsyncClient` sobre `ASGITransport(app=app)`, sin red real:

### `create_client()` *(recomendado — v1.2.0+)*

Async context manager que devuelve directamente el `httpx.AsyncClient`,
acepta cualquier kwarg de httpx:

```python
import pytest
from tachyon_api.testing import create_client

@pytest.mark.asyncio
async def test_async_endpoint():
    async with create_client(app) as client:
        response = await client.get("/hello")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_with_kwargs():
    async with create_client(
        app,
        headers={"X-Trace-Id": "abc"},
        cookies={"session": "s123"},
        auth=("user", "pass"),
        follow_redirects=True,
        timeout=10.0,
    ) as client:
        # Todos los kwargs son los de httpx.AsyncClient — base_url ya está seteado
        r = await client.get("/me")
```

### `AsyncTachyonTestClient`

Equivalente clase-based, mismas opciones:

```python
from tachyon_api.testing import AsyncTachyonTestClient

@pytest.mark.asyncio
async def test_async():
    async with AsyncTachyonTestClient(app, headers={"X-Token": "test"}) as client:
        response = await client.get("/users/1")
```

Cuál elegir es preferencia de estilo — `create_client` es el helper canónico
y el que usa la suite del framework + el example.

---

## 📝 Métodos HTTP

```python
client = TachyonTestClient(app)

# GET
response = client.get("/items")

# POST con JSON
response = client.post("/items", json={"name": "Widget"})

# PUT
response = client.put("/items/1", json={"name": "Updated"})

# DELETE
response = client.delete("/items/1")

# PATCH
response = client.patch("/items/1", json={"price": 9.99})
```

---

## 🔑 Headers

```python
# Headers custom
response = client.get(
    "/protected",
    headers={"Authorization": "Bearer token123"}
)

# Múltiples headers
response = client.get(
    "/api",
    headers={
        "Authorization": "Bearer token",
        "X-API-Key": "key123",
        "Accept-Language": "es"
    }
)
```

---

## ❓ Query Parameters

```python
# Método 1: en URL
response = client.get("/search?q=test&limit=10")

# Método 2: params dict
response = client.get(
    "/search",
    params={"q": "test", "limit": 10}
)
```

---

## 🍪 Cookies

```python
# Establecer cookies
client.cookies.set("session_id", "abc123")

# Request con cookie
response = client.get("/dashboard")

# Verificar cookies en response
assert response.cookies.get("new_session") == "xyz"
```

---

## 📁 File Uploads

```python
# Subir archivo
response = client.post(
    "/upload",
    files={"file": ("test.txt", b"content", "text/plain")}
)

# Con form data
response = client.post(
    "/upload",
    data={"title": "My File"},
    files={"file": ("doc.pdf", open("doc.pdf", "rb"), "application/pdf")}
)
```

---

## 🎭 Dependency Overrides

Mockear dependencias en tests:

```python
from tachyon_api import injectable, Depends

@injectable
class RealDatabase:
    def get_user(self, id: str):
        return {"id": id, "name": "Real User"}

class MockDatabase:
    def get_user(self, id: str):
        return {"id": id, "name": "Mock User"}

@app.get("/users/{user_id}")
def get_user(user_id: str, db: RealDatabase = Depends()):
    return db.get_user(user_id)

# Test con mock
def test_with_mock():
    # Override
    app.dependency_overrides[RealDatabase] = MockDatabase
    
    client = TachyonTestClient(app)
    response = client.get("/users/123")
    
    assert response.json()["name"] == "Mock User"
    
    # Limpiar (importante!)
    app.dependency_overrides.clear()
```

### Override con Lambda

```python
app.dependency_overrides[RealDatabase] = lambda: MockDatabase()
```

### Override Callable Dependencies

```python
def get_current_user():
    return {"id": "real_user"}

def mock_user():
    return {"id": "test_user"}

app.dependency_overrides[get_current_user] = mock_user
```

---

## 🔌 WebSocket Testing

```python
from starlette.testclient import TestClient

def test_websocket():
    client = TestClient(app)
    
    with client.websocket_connect("/ws") as ws:
        ws.send_text("Hello")
        response = ws.receive_text()
        assert response == "Echo: Hello"

def test_websocket_json():
    with TestClient(app).websocket_connect("/ws/json") as ws:
        ws.send_json({"type": "ping"})
        data = ws.receive_json()
        assert data["type"] == "pong"
```

---

## ⚡ Lifespan en Tests

El TestClient ejecuta lifespan automáticamente:

```python
from starlette.testclient import TestClient

def test_with_lifespan():
    # Startup se ejecuta al entrar
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
    # Shutdown se ejecuta al salir
```

---

## 📁 Fixtures con pytest

```python
# conftest.py
import pytest
from tachyon_api.testing import TachyonTestClient
from app import app

@pytest.fixture
def client():
    """Cliente de test."""
    return TachyonTestClient(app)

@pytest.fixture
def auth_client():
    """Cliente autenticado."""
    client = TachyonTestClient(app)
    # Login
    response = client.post("/login", json={"user": "test", "pass": "test"})
    token = response.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client

@pytest.fixture(autouse=True)
def clean_overrides():
    """Limpiar overrides después de cada test."""
    yield
    app.dependency_overrides.clear()
```

### Uso:
```python
def test_protected(auth_client):
    response = auth_client.get("/protected")
    assert response.status_code == 200
```

---

## 🗄️ Testing con Database

```python
import pytest

@pytest.fixture
def test_db():
    """Base de datos de test."""
    # Setup
    db = create_test_database()
    yield db
    # Teardown
    db.drop_all()

@pytest.fixture
def client(test_db):
    """Cliente con DB mockeada."""
    app.dependency_overrides[Database] = lambda: test_db
    yield TachyonTestClient(app)
    app.dependency_overrides.clear()
```

---

## 📋 Estructura Recomendada

```
tests/
├── __init__.py
├── conftest.py          # Fixtures compartidos
├── unit/
│   ├── test_services.py
│   └── test_repositories.py
├── integration/
│   ├── test_auth.py
│   └── test_users.py
└── e2e/
    └── test_flows.py
```

---

## 🔗 Próximos Pasos

- [CLI Tools](./12-cli.md) - Generar tests con CLI
- [Best Practices](./15-best-practices.md) - Patrones de testing
