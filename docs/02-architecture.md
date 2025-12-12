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

## 🔗 Próximos Pasos

- [Dependency Injection](./03-dependency-injection.md) - Cómo funciona `@injectable`
- [Parameters](./04-parameters.md) - Tipos de parámetros
