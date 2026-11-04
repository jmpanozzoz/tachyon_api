# 08. Lifecycle Events

> Eventos de startup y shutdown

## 🎯 Dos Formas de Usar

1. **`lifespan`** - Context manager (recomendado)
2. **`@app.on_event`** - Decoradores (simple)

---

## 🔄 Lifespan Context Manager

Ideal para recursos que necesitan cleanup:

```python
from tachyon_api import Tachyon, Body
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # === STARTUP ===
    print("🚀 Starting up...")
    
    # Conectar a base de datos
    app.state.db = await create_db_connection()
    
    # Inicializar cache
    app.state.cache = await create_cache()
    
    yield  # La app corre aquí
    
    # === SHUTDOWN ===
    print("🛑 Shutting down...")
    
    # Cerrar conexiones
    await app.state.db.close()
    await app.state.cache.close()

app = Tachyon(lifespan=lifespan)

@app.get("/")
def root():
    return {"status": "running"}
```

---

## 🎭 @app.on_event Decorators

Más simple, pero sin cleanup automático:

```python
from tachyon_api import Tachyon, Body

app = Tachyon()

@app.on_event("startup")
async def on_startup():
    print("🚀 App starting...")
    app.state.db = await create_connection()

@app.on_event("shutdown")
async def on_shutdown():
    print("🛑 App stopping...")
    await app.state.db.close()

# También funciona con funciones sync
@app.on_event("startup")
def sync_startup():
    print("Sync startup task")
```

---

## 💾 Usando app.state

`app.state` permite guardar objetos compartidos:

```python
from tachyon_api import Tachyon, Body
from contextlib import asynccontextmanager

# Simulación de conexiones
class DatabaseConnection:
    async def connect(self):
        print("DB Connected")
    
    async def close(self):
        print("DB Disconnected")
    
    async def query(self, sql):
        return {"result": sql}

@asynccontextmanager
async def lifespan(app):
    # Guardar en state
    app.state.db = DatabaseConnection()
    await app.state.db.connect()
    
    yield
    
    await app.state.db.close()

app = Tachyon(lifespan=lifespan)

@app.get("/data")
async def get_data():
    # Acceder desde cualquier endpoint
    result = await app.state.db.query("SELECT * FROM users")
    return result
```

---

## 🔌 Casos de Uso Comunes

### Conexión a Base de Datos

```python
from contextlib import asynccontextmanager
import asyncpg  # o tu driver favorito

@asynccontextmanager
async def lifespan(app):
    # Crear pool de conexiones
    app.state.pool = await asyncpg.create_pool(
        "postgresql://user:pass@localhost/db"
    )
    
    yield
    
    # Cerrar pool
    await app.state.pool.close()

app = Tachyon(lifespan=lifespan)
```

### Cliente HTTP

```python
import httpx
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Cliente HTTP reutilizable
    app.state.http_client = httpx.AsyncClient()
    
    yield
    
    await app.state.http_client.aclose()

app = Tachyon(lifespan=lifespan)

@app.get("/external")
async def call_external():
    response = await app.state.http_client.get("https://api.example.com")
    return response.json()
```

### Redis/Cache

```python
import redis.asyncio as redis
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    app.state.redis = redis.Redis.from_url("redis://localhost")
    
    yield
    
    await app.state.redis.close()

app = Tachyon(lifespan=lifespan)
```

### ML Models

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Cargar modelo (costoso, solo una vez)
    import torch
    app.state.model = torch.load("model.pt")
    app.state.model.eval()
    
    yield
    
    # Cleanup si es necesario
    del app.state.model

app = Tachyon(lifespan=lifespan)

@app.post("/predict")
def predict(data: InputData = Body()):
    return app.state.model(data.tensor)
```

---

## ⚡ Combinando Ambos

Puedes usar lifespan + on_event juntos:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    print("Lifespan startup")
    yield
    print("Lifespan shutdown")

app = Tachyon(lifespan=lifespan)

@app.on_event("startup")
def additional_startup():
    print("Additional startup task")

# Orden: on_event startup → lifespan startup → yield → lifespan shutdown → on_event shutdown
```

---

## 🧪 Testing con Lifespan

```python
from starlette.testclient import TestClient

def test_with_lifespan():
    # TestClient ejecuta lifespan automáticamente
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
```

---

## 📋 Resumen

| Método | Cuándo usar |
|--------|-------------|
| `lifespan` | Recursos que necesitan cleanup (DB, HTTP clients) |
| `@on_event("startup")` | Tareas simples de inicialización |
| `@on_event("shutdown")` | Tareas simples de cleanup |
| `app.state` | Compartir objetos entre endpoints |

---

## 🔗 Próximos Pasos

- [Background Tasks](./09-background-tasks.md) - Tareas async
- [Testing](./11-testing.md) - Testear con lifespan
