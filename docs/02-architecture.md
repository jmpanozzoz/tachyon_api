# 02. Architecture

> Arquitectura Clean para aplicaciones Tachyon escalables

## 🏗️ Estructura Recomendada

```
my-api/
├── app.py                  # Entry point
├── config.py               # Configuración
├── requirements.txt
│
├── modules/                # Feature modules
│   ├── __init__.py
│   ├── users/
│   │   ├── __init__.py
│   │   ├── users_controller.py   # Endpoints (Router)
│   │   ├── users_service.py      # Business logic
│   │   ├── users_repository.py   # Data access
│   │   ├── users_dto.py          # Data Transfer Objects
│   │   └── tests/
│   │       └── test_users_service.py
│   │
│   └── products/
│       ├── __init__.py
│       ├── products_controller.py
│       ├── products_service.py
│       ├── products_repository.py
│       └── products_dto.py
│
├── shared/                 # Shared utilities
│   ├── __init__.py
│   ├── exceptions.py       # Custom exceptions
│   ├── dependencies.py     # Shared dependencies
│   └── middleware.py       # Custom middleware
│
└── tests/
    ├── __init__.py
    └── conftest.py
```

---

## 📦 Capas de la Arquitectura

### 1. Controller (Presentation Layer)

Maneja HTTP requests/responses. Define endpoints y rutas.

```python
# modules/users/users_controller.py
from tachyon_api import Router, Depends
from .users_service import UsersService
from .users_dto import UserCreate, UserResponse

router = Router(prefix="/users", tags=["Users"])

@router.get("/", response_model=list[UserResponse])
def list_users(service: UsersService = Depends()):
    return service.get_all()

@router.post("/", response_model=UserResponse)
def create_user(data: UserCreate, service: UsersService = Depends()):
    return service.create(data)
```

### 2. Service (Business Layer)

Contiene la lógica de negocio. Orquesta repositorios.

```python
# modules/users/users_service.py
from tachyon_api import injectable, HTTPException
from .users_repository import UsersRepository
from .users_dto import UserCreate

@injectable
class UsersService:
    def __init__(self, repository: UsersRepository):
        self.repository = repository

    def get_all(self):
        return self.repository.find_all()

    def create(self, data: UserCreate):
        # Validaciones de negocio
        if self.repository.find_by_email(data.email):
            raise HTTPException(409, "Email already exists")
        return self.repository.create(data)
```

### 3. Repository (Data Layer)

Acceso a datos. Abstrae la base de datos.

```python
# modules/users/users_repository.py
from tachyon_api import injectable
from typing import Optional, List

@injectable
class UsersRepository:
    def __init__(self):
        self._db = {}  # Reemplazar con DB real

    def find_all(self) -> List[dict]:
        return list(self._db.values())

    def find_by_email(self, email: str) -> Optional[dict]:
        for user in self._db.values():
            if user["email"] == email:
                return user
        return None

    def create(self, data) -> dict:
        import uuid
        user_id = str(uuid.uuid4())
        user = {"id": user_id, **data.__dict__}
        self._db[user_id] = user
        return user
```

### 4. DTO (Data Transfer Objects)

Define la estructura de datos para requests/responses.

```python
# modules/users/users_dto.py
from tachyon_api import Struct
from typing import Optional

class UserBase(Struct):
    name: str
    email: str

class UserCreate(UserBase):
    password: str

class UserUpdate(Struct):
    name: Optional[str] = None
    email: Optional[str] = None

class UserResponse(UserBase):
    id: str
```

---

## 🔌 Registrar Módulos

En `app.py`:

```python
from tachyon_api import Tachyon

# Import routers
from modules.users import router as users_router
from modules.products import router as products_router

app = Tachyon()

# Register routers
app.include_router(users_router)
app.include_router(products_router)

@app.get("/")
def health():
    return {"status": "ok"}
```

---

## 🔧 Generar con CLI

```bash
# Generar módulo completo
tachyon g service users

# Con operaciones CRUD
tachyon g service products --crud
```

Esto crea automáticamente:
- `users_controller.py`
- `users_service.py`
- `users_repository.py`
- `users_dto.py`
- `tests/test_users_service.py`

---

## 🎯 Beneficios

| Beneficio | Descripción |
|-----------|-------------|
| **Separación de responsabilidades** | Cada capa tiene una única responsabilidad |
| **Testabilidad** | Fácil mockear dependencias |
| **Mantenibilidad** | Cambios aislados por capa |
| **Escalabilidad** | Agregar features sin afectar existentes |
| **Reusabilidad** | Services y repos reutilizables |

---

## 🧩 Tachyon's Internal Architecture (v1.2.x SRP refactor)

Tu *application* sigue el layout de arriba.  El **framework mismo** está
organizado por SRP — 63 módulos atómicos repartidos en paquetes con una
responsabilidad por archivo.  Cada pieza es candidata directa a `cdef class`
en v1.2.9.

```
tachyon_api/
├── app/                       # ASGI surface + composed collaborators
│   ├── __init__.py            # Tachyon facade (composes the rest)
│   ├── _asgi_entry.py         # __call__ — lazy HTTP-app build
│   ├── _http_dispatch.py      # HTTPDispatcher (HTTP vs WS/lifespan)
│   ├── _mw_stack.py           # MiddlewareStack
│   ├── _registry.py           # RouteRegistry
│   ├── _exception_table.py    # ExceptionTable (walks subclass handlers)
│   ├── _handler_factory.py    # closure for endpoints with params
│   ├── _fast_asgi_factory.py  # closure for no-param endpoints
│   ├── _route_installer.py    # trie + registry + openapi orchestration
│   ├── _docs_routes.py        # registers /docs /redoc /swagger /openapi.json
│   ├── _docs_schemas.py       # CommonSchemas (default error schemas)
│   ├── _asgi_handler.py       # _ASGIHandler marker (fast-path tag)
│   └── _404.py, _405.py       # pre-built ASGI constants
│
├── processing/                # request hot path
│   ├── compiler.py + .pyx     # endpoint pre-compilation
│   ├── parameters.py + .pyx   # ParameterPipeline orchestrator
│   ├── _extractors/           # 10 single-responsibility extractors
│   │   ├── body.py, body_limit.py, query.py, query_list.py,
│   │   ├── header.py, cookie.py, form.py, file.py, path.py,
│   │   ├── _base.py (ExtractorResult), _missing.py
│   ├── dependencies/          # DI pipeline (7 atomic pieces)
│   │   ├── _resolver.py, _override_lookup.py, _scope_cache.py,
│   │   ├── _circular_detector.py, _class_factory.py,
│   │   ├── _callable_factory.py, _sig_cache.py
│   ├── response_processor.py + .pyx
│   ├── scope.py + .pyx        # TachyonScope (lazy Starlette Request)
│   └── dispatch.py + .pyx     # TachyonDispatcher (cdef class)
│
├── responses/                 # response classes + caches + wire constants
│   ├── _json_response.py      # TachyonJSONResponse
│   ├── _bytes_response.py     # TachyonBytesResponse
│   ├── _internal_error.py     # _InternalErrorResponse singleton
│   ├── _caches.py             # _CL_CACHE, _CT_TUPLE precomputed
│   ├── _wire.py               # HTTP/1.1 wire bytes (TachyonServer path)
│   ├── _success.py, _error.py, _validation.py
│   └── _constants.py          # ASGI message-type strings, header bytes
│
├── openapi/                   # OpenAPI spec + 3 HTML renderers
│   ├── _generator.py, _route_builder.py
│   ├── _struct_schemas.py, _param_schemas.py
│   ├── _config.py, _factory.py, _info.py, _server.py
│   ├── _format_map.py, _safe_json.py
│   └── _swagger_html.py, _redoc_html.py, _scalar_html.py
│
├── security/                  # 4 auth schemes + value objects
│   ├── _http_bearer.py, _http_basic.py
│   ├── _api_key_header.py, _api_key_query.py, _api_key_cookie.py
│   ├── _oauth2_bearer.py
│   ├── _bearer_credentials.py, _basic_credentials.py
│   └── _bearer_parser.py, _api_key_base.py
│
├── routing/trie.py + .pyx     # radix trie router (Cython cdef)
├── core/lifecycle.py + websocket.py
├── middlewares/ (CORS, Logger, SecurityHeaders)
├── di.py                      # Depends + injectable + scope registries
├── models.py, params.py, exceptions.py, files.py, cache.py, background.py
├── _server_fast.pyx           # direct transport.write() fast path
└── cli/                       # commands + templates
```

**Hot path** = touched per HTTP request:
`Tachyon.__call__` → `ASGIEntry` → `HTTPDispatcher` → `TachyonDispatcher` (Cython) →
`ParameterPipeline` → `DependencyResolver` → `ResponseProcessor` →
`TachyonJSONResponse` / `TachyonBytesResponse`.

**Cold path** = touched at startup only:
`RouteInstaller`, `DocsRoutes`, `OpenAPIGenerator`, every class in `openapi/` and
`security/`, CLI.

Every hot-path class declares `__slots__` and every method has full type hints —
no import from the cold path into the hot path (verified in v1.2.7).

---

## 🔗 Próximos Pasos

- [Dependency Injection](./03-dependency-injection.md) - Cómo funciona `@injectable`
- [Parameters](./04-parameters.md) - Tipos de parámetros
- [Cython Build](./16-cython-build.md) - Compilar el hot path
