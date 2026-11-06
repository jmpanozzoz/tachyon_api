# 03. Dependency Injection

> Sistema de inyección de dependencias automático

## 🎯 Conceptos Básicos

Tachyon soporta dos tipos de inyección de dependencias:

1. **Implícita** - Con `@injectable` (tres scopes: `singleton`, `request`, `transient`)
2. **Explícita** - Con `Depends()` (factory por request, sync + async)

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
- ✅ **Recursivo** - Resuelve dependencias anidadas
- ✅ **Lazy** - Se crea cuando se necesita
- ✅ **Cycle detection** - levanta `TypeError: Circular dependency detected ...`
- ✅ **Scopes** - `singleton` (default), `request`, `transient` — ver sección siguiente

---

## 🔁 Scopes (v1.2.0+)

`@injectable` acepta un keyword `scope` con tres valores:

```python
from tachyon_api import injectable

@injectable                           # equivalente a @injectable(scope="singleton")
class DB:
    """One instance per application — shared across all requests."""

@injectable(scope="request")
class RequestContext:
    """One instance per HTTP request — cached in the request's dependency_cache."""
    def __init__(self):
        import uuid
        self.correlation_id = str(uuid.uuid4())

@injectable(scope="transient")
class IdGenerator:
    """New instance on every injection — never cached."""
    def __init__(self):
        self._seq = 0
```

### Cuándo usar cada uno

| Scope | Cuándo usarlo | Ejemplos |
|-------|---------------|----------|
| **`singleton`** *(default)* | Estado app-wide, conexiones costosas | DB pool, settings, HTTP clients, caches |
| **`request`** | Estado por-request compartido entre deps | Correlation IDs, parsed auth claims, per-request feature flags |
| **`transient`** | Builders / generadores que no deben compartir estado | UUID/ID generators, BulkRequestBuilder, EmailComposer |

Una clase `request` que depende de otra clase `request` comparte su instancia dentro de la solicitud (o conexión WebSocket). Un constructor singleton solo puede capturar clases singleton: Request/WebSocket, clases request/transient y factories por request se rechazan al registrar para evitar retener contexto de la primera solicitud.

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
- ✅ **Async-aware** - Si el factory devuelve una coroutine, Tachyon la awaitea

### Async dependencies

`Depends(async_fn)` funciona transparentemente:

```python
async def get_user(token: str = Header(...)):
    return await verify_token_async(token)

@app.get("/me")
async def me(user: dict = Depends(get_user)):   # await automático
    return user
```

> **Versiones:** 1.4.x rechaza dependencias generadoras. La candidata 1.5 admite
> `yield` en HTTP con limpieza por petición; WebSocket sigue usando lifespan.

---

## 🚨 Exception handlers para clases derivadas de HTTPException (v1.2.811+)

Podés registrar handlers para SUBCLASES de `HTTPException` y Tachyon
los va a despachar correctamente:

```python
from tachyon_api import Tachyon, HTTPException
from starlette.responses import JSONResponse

class KYCException(HTTPException):
    def __init__(self, status_code, detail, error_code):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code

class CustomerNotFoundError(KYCException):
    def __init__(self, customer_id):
        super().__init__(404, f"Customer {customer_id} not found", "CUSTOMER_NOT_FOUND")

app = Tachyon()

@app.exception_handler(KYCException)        # captura todas las subclases
async def kyc_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail, "code": exc.error_code},
    )
```

`ExceptionTable.dispatch` itera los handlers registrados en orden de
inserción y elige el primer `isinstance` match.  Si nada matchea pero
la excepción ES `HTTPException`, vuelve al body default `{"detail": ...}`.

Antes de v1.2.811 este handler nunca se ejecutaba: la dispatch hacía
short-circuit al default response apenas veía un HTTPException.  Si
estás migrando desde una versión anterior, los handlers para subclases
ahora SÍ disparan — ojo con cambios de body shape.

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
| Implícita | `@injectable` | Singleton *(default)* | Services, Repositories, DB pools |
| Implícita | `@injectable(scope="request")` | Per-request | Correlation IDs, parsed auth context |
| Implícita | `@injectable(scope="transient")` | New per injection | Builders, ID generators |
| Explícita | `Depends(callable)` | Per-request | Auth, Factories, sync + async |
| Override | `app.dependency_overrides` | Testing | Mocks |

---

## 🔗 Próximos Pasos

- [Parameters](./04-parameters.md) - Parámetros de entrada
- [Security](./06-security.md) - Autenticación

## Contrato de factories y lifetimes

Las factories admiten Request/WebSocket tipados, Depends anidados, clases registradas, defaults Python y extracción HTTP con Header/Query. Body/Form/File/Cookie/Path dentro de factories se rechazan al registrar; usar Request y lectura explícita si hace falta. En WebSocket, usar WebSocket tipado para acceso a headers/query. Los scopes inválidos se rechazan al registrar. Desde la candidata 1.5, generators (`yield`) se admiten solo en HTTP; WebSocket los rechaza al registrar.

Singleton se construye de forma lazy en su primer uso y se comparte en la aplicación. Debe soportar acceso concurrente desde los threads de handlers sync; no debe conservar datos de usuario. El scope request en WebSocket dura la conexión, no el mensaje.


The low-level synchronous `DependencyResolver.resolve_dependency` entry point is
for startup/bootstrap code before request serving. Concurrent synchronous calls
are serialized per singleton, but do not mix it concurrently with the asynchronous
resolver on the same application. HTTP and WebSocket dispatch use the asynchronous
resolver. Configure overrides before serving; tests that change them must isolate
their application and restore configuration before the next test.


## Recursos HTTP con yield — candidata 1.5

Esta capacidad no está publicada en 1.4.3. Un proveedor generador debe producir
exactamente un valor. Se adquiere una vez por dependencia cacheada/petición y se
cierra en orden inverso al completar respuesta y background tasks, también ante
error, disconnect o cancelación. Los recursos siguen disponibles durante streaming.

```python
from tachyon_api import Depends, Tachyon

app = Tachyon()

async def resource():
    value = {"open": True}
    try:
        yield value
    finally:
        value["open"] = False

@app.get("/resource")
async def show(value=Depends(resource)):
    return {"open": value["open"]}
```

Las dependencias sync entran/salen en un thread pool sin afinidad garantizada;
no usar recursos que exijan el mismo thread. La salida usa un limitador separado
para evitar deadlock con el pool de adquisición. La limpieza async está acotada
a 10 segundos con protección de cancelación cooperativa; Python no puede matar
un thread bloqueado, que puede continuar tras agotar el plazo.

Una clase singleton no puede capturar estos proveedores. Una clase que necesita
sesión de DB debe ser request-scoped. Una AsyncSession pertenece a una tarea;
abrir sesiones independientes para trabajo concurrente o jobs. Los WebSockets y
la resolución de bootstrap sin petición HTTP rechazan proveedores generadores.

Confirmar la transacción antes de devolver una respuesta exitosa. La salida
libera recursos y revierte trabajo pendiente, no confirma escrituras después de
un 2xx. Las excepciones del endpoint llegan al generador incluso si ya tienen
respuesta de error; no suprimirlas para convertir operaciones fallidas en éxito.
Un error de salida tras enviar cabeceras no puede cambiar el status; se propaga o
se registra preservando el error original. No usar la salida para lógica de
negocio cuyo resultado deba conocer el cliente.
