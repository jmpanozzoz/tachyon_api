# 07. Caching

> Sistema de cache con decorador `@cache`

## 🎯 Uso Básico

```python
from tachyon_api import Tachyon, cache

app = Tachyon()

@app.get("/expensive")
@cache(ttl=60)  # Cache por 60 segundos
def expensive_operation():
    # Operación costosa
    import time
    time.sleep(2)
    return {"data": "result", "computed_at": time.time()}
```

Primera request: ~2 segundos
Siguientes requests (dentro de 60s): ~0ms

---

## ⚙️ Configuración

### Cache Config Global

```python
from tachyon_api import Tachyon, CacheConfig, create_cache_config

cache_config = create_cache_config(
    default_ttl=300,  # 5 minutos por defecto
    max_size=1000,    # Máximo 1000 entries
)

app = Tachyon(cache_config=cache_config)
```

### Backends Disponibles

```python
from tachyon_api import (
    InMemoryCacheBackend,
    RedisCacheBackend,
    MemcachedCacheBackend,
)

# In-Memory (default)
backend = InMemoryCacheBackend()

# Redis
backend = RedisCacheBackend(url="redis://localhost:6379/0")

# Memcached
backend = MemcachedCacheBackend(servers=["localhost:11211"])
```

---

## 🔑 Cache Keys

Por defecto, la key se genera desde los argumentos:

```python
@app.get("/users/{user_id}")
@cache(ttl=120)
def get_user(user_id: str):
    return {"user_id": user_id}

# GET /users/123 → cache key incluye "123"
# GET /users/456 → cache key diferente
```

### Custom Key

```python
@app.get("/data")
@cache(ttl=60, key="custom_key")
def get_data():
    return {"data": "value"}
```

### Key con Función

```python
def make_cache_key(*args, **kwargs):
    return f"user:{kwargs.get('user_id')}"

@app.get("/users/{user_id}")
@cache(ttl=60, key=make_cache_key)
def get_user(user_id: str):
    return {"user_id": user_id}
```

---

## 🔄 Invalidación Manual

```python
from tachyon_api import get_cache_config

# Obtener instancia del cache
cache_instance = get_cache_config()

# Invalidar una key específica
await cache_instance.delete("my_cache_key")

# Invalidar por patrón (si el backend lo soporta)
await cache_instance.delete_pattern("user:*")
```

---

## ⏰ TTL Dinámico

```python
import random

@app.get("/dynamic")
@cache(ttl=lambda: random.randint(60, 300))
def dynamic_ttl():
    return {"cached": True}
```

---

## 🚫 Condicional

Cache solo bajo ciertas condiciones:

```python
@app.get("/conditional")
@cache(
    ttl=60,
    condition=lambda result: result.get("success", False)
)
def conditional_cache():
    # Solo se cachea si success=True
    return {"success": True, "data": "..."}
```

---

## 📊 Ejemplo Completo

```python
from tachyon_api import (
    Tachyon,
    cache,
    CacheConfig,
    create_cache_config,
    Query,
)

# Configurar cache
cache_config = create_cache_config(default_ttl=300)
app = Tachyon(cache_config=cache_config)

# Datos simulados
def fetch_from_database(id: str):
    import time
    time.sleep(0.5)  # Simular latencia DB
    return {"id": id, "name": f"Item {id}"}

# Endpoint cacheado
@app.get("/items/{item_id}")
@cache(ttl=120)
def get_item(item_id: str):
    return fetch_from_database(item_id)

# Lista con cache
@app.get("/items")
@cache(ttl=60)
def list_items(page: int = Query(1), limit: int = Query(10)):
    # La key incluirá page y limit
    return {
        "items": [f"item_{i}" for i in range(limit)],
        "page": page
    }

# Sin cache (operaciones de escritura)
@app.post("/items")
def create_item():
    # POST/PUT/DELETE no se cachean
    return {"created": True}
```

---

## 🧪 Testing con Cache

```python
from tachyon_api.testing import TachyonTestClient

def test_cached_endpoint():
    client = TachyonTestClient(app)
    
    # Primera llamada
    response1 = client.get("/items/123")
    
    # Segunda llamada (debería ser cacheada)
    response2 = client.get("/items/123")
    
    assert response1.json() == response2.json()
```

---

## 📋 Resumen

| Opción | Descripción | Default |
|--------|-------------|---------|
| `ttl` | Tiempo de vida en segundos | Config global |
| `key` | Key manual o función | Auto-generada |
| `condition` | Función para decidir si cachear | `True` |
| `backend` | Backend de cache | `InMemoryCacheBackend` |

---

## 🔗 Próximos Pasos

- [Lifecycle Events](./08-lifecycle.md) - Inicializar cache en startup
- [Background Tasks](./09-background-tasks.md) - Invalidar cache async
