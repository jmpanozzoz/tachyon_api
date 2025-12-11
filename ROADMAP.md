# 🚀 Tachyon API - Roadmap to v0.7.x

Este documento describe el plan de trabajo para llevar Tachyon API desde v0.5.x hasta una release estable v0.7.x lista para producción.

## 📋 Principios de Desarrollo

- **TDD (Test-Driven Development)**: Escribir tests ANTES de implementar cada feature
- **Clean Code**: Código legible, bien documentado, sin duplicación
- **Backward Compatibility**: Mantener compatibilidad con código existente
- **Incremental Releases**: Releases pequeñas y frecuentes

---

## 🧹 FASE 0 - Cleanup & Refactoring (Pre-0.6.0)

> **Objetivo**: Limpiar código duplicado, eliminar código muerto, preparar base sólida

### Issues Identificados

| Issue | Ubicación | Acción |
|-------|-----------|--------|
| `_unwrap_optional` duplicado | `openapi.py` + `type_utils.py` | Eliminar de openapi.py, usar TypeUtils |
| `TYPE_MAP` / `type_map` duplicado | `openapi.py` + `app.py` | Centralizar en módulo de utils |
| `_get_openapi_type` duplicado | `app.py` | Reusar desde openapi.py |
| Lógica List/Union duplicada | Múltiples archivos | Centralizar en TypeUtils |
| `_generate_schema_for_struct` | `openapi.py` | Código muerto, eliminar |
| `typer` dependency | `pyproject.toml` | No usado - implementar CLI o eliminar |
| Imports inconsistentes | Varios archivos | Unificar estilo `from typing import` |
| HTMLResponse duplicado | `app.py` + `responses.py` | Importar desde responses.py |
| `_build_param_openapi_schema` | `app.py` | Mover a openapi.py |

### Tareas

- [ ] 0.1 - Eliminar `_unwrap_optional` de openapi.py → usar `TypeUtils.unwrap_optional`
- [ ] 0.2 - Crear `TYPE_MAPPING` centralizado en `tachyon_api/utils/type_utils.py`
- [ ] 0.3 - Eliminar `_get_openapi_type` de app.py → importar desde openapi.py
- [ ] 0.4 - Agregar helpers a TypeUtils: `is_optional`, `is_list_type`, `get_list_item_type`
- [ ] 0.5 - Eliminar `_generate_schema_for_struct` (código muerto)
- [ ] 0.6 - Mantener typer para CLI en 0.6.6
- [ ] 0.7 - Unificar imports a estilo `from typing import X, Y, Z`
- [ ] 0.8 - Importar `HTMLResponse` desde responses.py en app.py
- [ ] 0.9 - Mover `_build_param_openapi_schema` a openapi.py
- [ ] 0.10 - ✅ Ejecutar tests - TODOS deben pasar antes de continuar

---

## 🎯 RELEASE 0.6.0 - Foundation (Request/Params)

> **Objetivo**: Completar el sistema de parámetros con Request, Header, Cookie y mejorar DI

### Features

#### 1. Request Object Injection
```python
from tachyon_api import Tachyon
from starlette.requests import Request

app = Tachyon()

@app.get("/info")
def get_info(request: Request):
    return {
        "client": request.client.host,
        "headers": dict(request.headers),
        "url": str(request.url)
    }
```

#### 2. Header() Parameter
```python
from tachyon_api import Header

@app.get("/protected")
def protected(authorization: str = Header(...), x_request_id: str = Header(None)):
    return {"auth": authorization, "request_id": x_request_id}
```

#### 3. Cookie() Parameter
```python
from tachyon_api import Cookie

@app.get("/profile")
def profile(session_id: str = Cookie(...)):
    return {"session": session_id}
```

#### 4. Depends(callable)
```python
from tachyon_api import Depends

def get_db():
    db = Database()
    try:
        yield db
    finally:
        db.close()

@app.get("/users")
def get_users(db: Database = Depends(get_db)):
    return db.query_all()
```

### Tareas TDD

- [ ] 1.0 - TEST: `test_request_injection.py` - Request object disponible en endpoint
- [ ] 1.1 - IMPL: Detectar `Request` en signature e inyectar automáticamente
- [ ] 1.2 - TEST: `test_header_params.py` - Header extraction y validación
- [ ] 1.3 - IMPL: `Header()` class en params.py + handler en app.py
- [ ] 1.4 - TEST: `test_cookie_params.py` - Cookie extraction y validación
- [ ] 1.5 - IMPL: `Cookie()` class en params.py + handler en app.py
- [ ] 1.6 - TEST: `test_depends_callable.py` - Factory functions como dependencias
- [ ] 1.7 - IMPL: Modificar `Depends` para aceptar callable + generators
- [ ] 1.8 - Actualizar `__init__.py` exports, CHANGELOG, README

---

## 🔄 RELEASE 0.6.1 - Lifecycle Events

> **Objetivo**: Soportar inicialización y cleanup de recursos (DB, connections, etc.)

### Features

#### 1. Lifespan Context Manager
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Startup
    await database.connect()
    yield
    # Shutdown
    await database.disconnect()

app = Tachyon(lifespan=lifespan)
```

#### 2. on_event Decorators (Legacy API)
```python
@app.on_event("startup")
async def startup():
    await cache.init()

@app.on_event("shutdown")
async def shutdown():
    await cache.close()
```

### Tareas TDD

- [ ] 2.0 - TEST: `test_lifespan.py` - startup/shutdown ejecutados correctamente
- [ ] 2.1 - IMPL: Pasar lifespan a Starlette internamente
- [ ] 2.2 - TEST: `test_on_event.py` - decorators registran handlers
- [ ] 2.3 - IMPL: `on_event()` decorator que construye lifespan
- [ ] 2.4 - Actualizar CHANGELOG, README

---

## 📁 RELEASE 0.6.2 - File Handling

> **Objetivo**: Soportar file uploads y form data

### Features

#### 1. UploadFile
```python
from tachyon_api import UploadFile, File

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    contents = await file.read()
    return {"filename": file.filename, "size": len(contents)}
```

#### 2. Form Data
```python
from tachyon_api import Form

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    return {"user": username}
```

### Tareas TDD

- [ ] 3.0 - TEST: `test_file_upload.py` - Single y multiple file upload
- [ ] 3.1 - IMPL: `UploadFile` class (wrapper sobre Starlette)
- [ ] 3.2 - TEST: `test_form_data.py` - Form fields extraction
- [ ] 3.3 - IMPL: `Form()` class en params.py
- [ ] 3.4 - IMPL: `File()` class en params.py
- [ ] 3.5 - IMPL: Multipart parser integration en handler
- [ ] 3.6 - Actualizar CHANGELOG, README

---

## 🚨 RELEASE 0.6.3 - Exception Handling

> **Objetivo**: Sistema flexible de manejo de excepciones

### Features

#### 1. HTTPException
```python
from tachyon_api import HTTPException

@app.get("/items/{item_id}")
def get_item(item_id: int):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return items[item_id]
```

#### 2. Custom Exception Handlers
```python
class ItemNotFoundError(Exception):
    def __init__(self, item_id: int):
        self.item_id = item_id

@app.exception_handler(ItemNotFoundError)
async def item_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": f"Item {exc.item_id} not found"}
    )
```

### Tareas TDD

- [ ] 4.0 - TEST: `test_http_exception.py` - HTTPException retorna status correcto
- [ ] 4.1 - IMPL: `HTTPException` class en exceptions.py
- [ ] 4.2 - TEST: `test_exception_handlers.py` - Custom handlers invocados
- [ ] 4.3 - IMPL: `_exception_handlers` registry en Tachyon
- [ ] 4.4 - IMPL: `@app.exception_handler()` decorator
- [ ] 4.5 - Actualizar CHANGELOG, README

---

## 🔒 RELEASE 0.6.4 - Security Foundation

> **Objetivo**: Sistema de autenticación y autorización

### Features

#### 1. HTTP Bearer
```python
from tachyon_api.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.get("/protected")
def protected(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    return {"token": token}
```

#### 2. OAuth2 Password Bearer
```python
from tachyon_api.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.get("/users/me")
def get_current_user(token: str = Depends(oauth2_scheme)):
    return decode_token(token)
```

#### 3. API Key
```python
from tachyon_api.security import APIKeyHeader

api_key = APIKeyHeader(name="X-API-Key")

@app.get("/data")
def get_data(key: str = Depends(api_key)):
    return {"data": "secret"}
```

### Tareas TDD

- [ ] 5.0 - Crear `tachyon_api/security.py`
- [ ] 5.1 - TEST: `test_security_base.py`
- [ ] 5.2 - IMPL: `SecurityBase` class
- [ ] 5.3 - TEST: `test_http_bearer.py`
- [ ] 5.4 - IMPL: `HTTPBearer`, `HTTPBasic`
- [ ] 5.5 - TEST: `test_oauth2.py`
- [ ] 5.6 - IMPL: `OAuth2PasswordBearer`
- [ ] 5.7 - IMPL: `APIKeyHeader`, `APIKeyQuery`, `APIKeyCookie`
- [ ] 5.8 - IMPL: OpenAPI security schemes
- [ ] 5.9 - Actualizar CHANGELOG, README

---

## ⚡ RELEASE 0.6.5 - Background Tasks

> **Objetivo**: Ejecutar tareas después de enviar la respuesta

### Features

```python
from tachyon_api import BackgroundTasks

def send_email(email: str, message: str):
    # Enviar email (tarea lenta)
    ...

@app.post("/notify")
def notify(email: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(send_email, email, "Welcome!")
    return {"status": "Notification queued"}
```

### Tareas TDD

- [ ] 6.0 - TEST: `test_background_tasks.py` - Tasks ejecutadas post-response
- [ ] 6.1 - IMPL: `BackgroundTasks` class (wrapper sobre Starlette)
- [ ] 6.2 - IMPL: Auto-injection cuando se detecta en signature
- [ ] 6.3 - Actualizar CHANGELOG, README

---

## 🔧 RELEASE 0.6.6 - CLI Tools

> **Objetivo**: Herramientas de línea de comandos para productividad

### Features

```bash
# Run server con hot-reload
tachyon run app:app --reload --port 8000

# Crear nuevo proyecto
tachyon new myproject
# Genera:
# myproject/
#   ├── app.py
#   ├── routers/
#   ├── models/
#   ├── services/
#   └── requirements.txt

# Exportar OpenAPI schema
tachyon openapi app:app --output openapi.json
```

### Tareas

- [ ] 7.0 - Crear `tachyon_api/cli.py` con Typer
- [ ] 7.1 - IMPL: `tachyon run` command
- [ ] 7.2 - IMPL: `tachyon new` command con templates
- [ ] 7.3 - IMPL: `tachyon openapi` command
- [ ] 7.4 - Agregar entry point en pyproject.toml
- [ ] 7.5 - Actualizar CHANGELOG, README

---

## 🧪 RELEASE 0.6.7 - Testing Utilities

> **Objetivo**: Facilitar testing de aplicaciones Tachyon

### Features

```python
from tachyon_api.testing import TachyonTestClient

def test_read_main():
    client = TachyonTestClient(app)
    response = client.get("/")
    assert response.status_code == 200

# Dependency overrides
def override_get_db():
    return MockDatabase()

app.dependency_overrides[get_db] = override_get_db
```

### Tareas

- [ ] 8.0 - Crear `tachyon_api/testing.py`
- [ ] 8.1 - IMPL: `TachyonTestClient` wrapper
- [ ] 8.2 - IMPL: `app.dependency_overrides` dict
- [ ] 8.3 - Actualizar CHANGELOG, README

---

## 🌐 RELEASE 0.7.0 - WebSockets

> **Objetivo**: Soporte para comunicación bidireccional en tiempo real

### Features

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")
```

### Tareas TDD

- [ ] 9.0 - TEST: `test_websocket.py` - Connection, send, receive
- [ ] 9.1 - IMPL: `@app.websocket()` decorator
- [ ] 9.2 - IMPL: `WebSocket` class wrapper
- [ ] 9.3 - IMPL: WebSocket support en Router
- [ ] 9.4 - Actualizar CHANGELOG, README

---

## 📚 RELEASE 0.7.x - Documentation & Polish

> **Objetivo**: Documentación completa y material de marketing

### Tareas

- [ ] 10.1 - Setup MkDocs con Material theme
- [ ] 10.2 - Tutorial: Quick Start (5 minutos)
- [ ] 10.3 - Tutorial: Path/Query/Body Parameters
- [ ] 10.4 - Tutorial: Dependency Injection
- [ ] 10.5 - Tutorial: Security & Authentication
- [ ] 10.6 - Tutorial: Testing Your App
- [ ] 10.7 - Benchmarks publicados vs FastAPI
- [ ] 10.8 - Migration Guide from FastAPI
- [ ] 10.9 - Deployment Guides (Docker, systemd, Kubernetes)
- [ ] 10.10 - Deploy docs a GitHub Pages

---

## 📊 Timeline Estimado

| Release | Features | Estimación |
|---------|----------|------------|
| Fase 0 | Cleanup | 1-2 días |
| 0.6.0 | Request/Header/Cookie/Depends | 3-4 días |
| 0.6.1 | Lifespan Events | 1-2 días |
| 0.6.2 | File Handling | 2-3 días |
| 0.6.3 | Exception Handling | 2 días |
| 0.6.4 | Security | 4-5 días |
| 0.6.5 | Background Tasks | 1 día |
| 0.6.6 | CLI Tools | 2-3 días |
| 0.6.7 | Testing Utils | 1-2 días |
| 0.7.0 | WebSockets | 2-3 días |
| 0.7.x | Documentation | 5-7 días |

**Total estimado**: ~25-35 días de desarrollo

---

## 🎯 Definition of Done

Cada feature se considera completo cuando:

1. ✅ Tests escritos ANTES de la implementación (TDD)
2. ✅ Implementación pasa todos los tests
3. ✅ Sin código duplicado
4. ✅ Documentado con docstrings
5. ✅ Agregado a `__init__.py` exports
6. ✅ CHANGELOG actualizado
7. ✅ README actualizado si aplica
8. ✅ Example app actualizada si aplica

---

*Documento generado el $(date). Actualizar según avance del desarrollo.*
