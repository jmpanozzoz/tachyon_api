# 02. Architecture

> Arquitectura Clean para aplicaciones Tachyon escalables

## 🏗️ Estructura Recomendada

```
my_api/
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
from tachyon_api import Router, Depends, Body
from .users_service import UsersService
from .users_dto import UserCreate, UserResponse

router = Router(prefix="/users", tags=["Users"])

@router.get("/", response_model=list[UserResponse])
def list_users(service: UsersService = Depends()):
    return service.get_all()

@router.post("/", response_model=UserResponse)
def create_user(data: UserCreate = Body(), service: UsersService = Depends()):
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
import msgspec
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
        user = {"id": user_id, **msgspec.structs.asdict(data)}
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

Cada paquete de módulo debe exportar su router desde `__init__.py`, por ejemplo `from .users_controller import router` en `modules/users/__init__.py`. Luego, en `app.py`:

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
tachyon g service user

# Con operaciones CRUD
tachyon g service product --crud
```

Para `tachyon g service user`, esto crea automáticamente:
- `user_controller.py`
- `user_service.py`
- `user_repository.py`
- `user_dto.py`
- `tests/test_user_service.py`

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

## Arquitectura interna actual

- `app/`: facade ASGI, registro de rutas, middleware, errores y factories de handlers.
- `processing/compiler.py`: metadatos y decoders preparados al registrar.
- `processing/parameters.py`: `ParameterProcessor`; extractores en `_extractors/` devuelven tuples.
- `processing/dependencies/`: factories, scopes, overrides y resolución de firmas.
- `processing/scope.py` y `_request.py`: recepción acotada, cache de Request y lifetime multipart.
- `routing/trie.py`: prioridad estática con fallback si una rama no completa la ruta.
- `responses/`: mensajes ASGI por envío; `_internal_error.py` crea respuestas por llamada. `app/_error_static.py` contiene constantes de errores estáticos.
- `openapi/`: schemas, `_config.py` y `_html_renderers.py` para el subconjunto OpenAPI 3.0 admitido.
- `security/`: extracción de credenciales; API keys en `_api_keys.py`, valores en `_credentials.py`.
- `core/`: lifecycle y WebSockets delegados a Starlette.
- `server.py`: runner compatible con Uvicorn estándar.

HTTP normal: `ASGIEntry` → stack propio de middleware → `TachyonDispatcher`
→ guards → `ParameterProcessor`/`DependencyResolver` → `ResponseProcessor`.
`HTTPDispatcher` corresponde al flujo de compatibilidad Starlette.
Los endpoints y factories sync se ejecutan en un thread pool; los async se awaitean.

`RouteInstaller.install` compila las rutas al registrarlas. La configuración de
docs se instala de forma lazy al primer scope; el HTML se renderiza al pedirlo.
Los extractores de seguridad se ejecutan por solicitud durante DI, no solo al
arrancar. No se promete costo constante ni un multiplicador de rendimiento.

- [Dependency Injection](03-dependency-injection.md)
- [Request Lifecycle](13-request-lifecycle.md)
- [Portable builds](16-cython-build.md)
