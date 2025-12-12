# 03. Dependency Injection

> Sistema de inyección de dependencias automático

## 🎯 Conceptos Básicos

Tachyon soporta dos tipos de inyección de dependencias:

1. **Implícita** - Con `@injectable` (singleton)
2. **Explícita** - Con `Depends()` (por request)

---

## 📦 Inyección Implícita con @injectable

Marca una clase como inyectable y Tachyon la resuelve automáticamente:

```python
from tachyon_api import Tachyon, injectable, Depends

@injectable
class Database:
    def __init__(self):
        self.connection = "connected"
    
    def query(self, sql: str):
        return f"Executing: {sql}"

@injectable
class UserRepository:
    def __init__(self, db: Database):  # Database se inyecta automáticamente
        self.db = db
    
    def find_all(self):
        return self.db.query("SELECT * FROM users")

app = Tachyon()

@app.get("/users")
def get_users(repo: UserRepository = Depends()):
    return {"users": repo.find_all()}
```

### Características:
- ✅ **Singleton** - Una instancia por aplicación
- ✅ **Recursivo** - Resuelve dependencias anidadas
- ✅ **Lazy** - Se crea cuando se necesita

---

## 🔄 Inyección Explícita con Depends()

Para factories o funciones que retornan valores:

```python
from tachyon_api import Tachyon, Depends, Header, HTTPException

def get_current_user(authorization: str = Header(...)):
    """Factory function que extrae el usuario del token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid token")
    
    token = authorization[7:]
    # Validar token y retornar usuario
    return {"user_id": "123", "name": "John"}

app = Tachyon()

@app.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return user

@app.get("/profile")
def get_profile(user: dict = Depends(get_current_user)):
    return {"profile": user["name"]}
```

### Características:
- ✅ **Por request** - Se ejecuta en cada request
- ✅ **Cacheable** - Mismo callable = mismo resultado por request
- ✅ **Async** - Soporta funciones async

---

## 🔗 Dependencias Anidadas

Las dependencias pueden depender de otras:

```python
from tachyon_api import Tachyon, Depends, Header

def get_token(authorization: str = Header(...)) -> str:
    return authorization.replace("Bearer ", "")

def get_user(token: str = Depends(get_token)) -> dict:
    # Decodificar token
    return {"id": "user_123", "token": token}

def get_permissions(user: dict = Depends(get_user)) -> list:
    # Obtener permisos del usuario
    return ["read", "write"]

app = Tachyon()

@app.get("/admin")
def admin_panel(
    user: dict = Depends(get_user),
    permissions: list = Depends(get_permissions)
):
    return {"user": user, "permissions": permissions}
```

---

## 🎭 Dependency Overrides (Testing)

Para tests, puedes reemplazar dependencias:

```python
from tachyon_api import Tachyon, injectable, Depends
from tachyon_api.testing import TachyonTestClient

@injectable
class RealDatabase:
    def get_data(self):
        return "real data from DB"

class MockDatabase:
    def get_data(self):
        return "mock data"

app = Tachyon()

@app.get("/data")
def get_data(db: RealDatabase = Depends()):
    return {"data": db.get_data()}

# En tests
def test_with_mock():
    app.dependency_overrides[RealDatabase] = MockDatabase
    
    client = TachyonTestClient(app)
    response = client.get("/data")
    assert response.json() == {"data": "mock data"}
    
    # Limpiar
    app.dependency_overrides.clear()
```

---

## 🏭 Patrones Comunes

### Inyectar Request

```python
from tachyon_api import Tachyon
from starlette.requests import Request

app = Tachyon()

@app.get("/info")
def request_info(request: Request):
    return {
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers)
    }
```

### Inyectar Configuración

```python
from tachyon_api import injectable, Depends

@injectable
class Settings:
    def __init__(self):
        import os
        self.debug = os.getenv("DEBUG", "false") == "true"
        self.db_url = os.getenv("DATABASE_URL", "sqlite:///./app.db")

@app.get("/config")
def get_config(settings: Settings = Depends()):
    return {"debug": settings.debug}
```

### Security Dependencies

```python
from tachyon_api import Depends, HTTPException
from tachyon_api.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = decode_token(token)  # Tu lógica
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

@app.get("/protected")
def protected(user: dict = Depends(get_current_user)):
    return {"user": user}
```

---

## 📋 Resumen

| Tipo | Decorador/Función | Scope | Uso |
|------|-------------------|-------|-----|
| Implícita | `@injectable` | Singleton | Services, Repositories |
| Explícita | `Depends(callable)` | Per-request | Auth, Factories |
| Override | `app.dependency_overrides` | Testing | Mocks |

---

## 🔗 Próximos Pasos

- [Parameters](./04-parameters.md) - Parámetros de entrada
- [Security](./06-security.md) - Autenticación
