# 15. Best Practices

> Patrones y recomendaciones para Tachyon

## 🏗️ Arquitectura

### ✅ Usar Clean Architecture

```
modules/
└── users/
    ├── users_controller.py   # Solo HTTP, delega a service
    ├── users_service.py      # Lógica de negocio
    ├── users_repository.py   # Acceso a datos
    └── users_dto.py          # Modelos de datos
```

### ❌ Evitar

```python
# No pongas lógica de negocio en el controller
@app.post("/users")
def create_user(user: UserCreate = Body()):
    # ❌ Validación de negocio aquí
    if "@" not in user.email:
        raise HTTPException(400, "Invalid email")
    
    # ❌ Acceso a DB aquí
    db.execute("INSERT INTO users ...")
```

### ✅ Mejor

```python
@app.post("/users")
def create_user(user: UserCreate = Body(), service: UserService = Depends()):
    return service.create(user)  # ✅ Delegar al service
```

---

## 📦 Dependency Injection

### ✅ Usar @injectable para Services/Repos

```python
@injectable
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo
```

### ✅ Usar Depends(callable) para Request-scoped

```python
def get_current_user(token: str = Depends(oauth2_scheme)):
    return decode_token(token)

@app.get("/me")
def me(user: User = Depends(get_current_user)):
    return user
```

### ❌ Evitar: Instanciar manualmente

```python
# ❌ No hagas esto
@app.get("/users")
def get_users():
    service = UserService(UserRepository())  # ❌
    return service.get_all()
```

---

## 📝 Modelos

### ✅ Separar DTOs por propósito

```python
class UserCreate(Struct):
    email: str
    password: str

class UserUpdate(Struct):
    email: Optional[str] = None
    name: Optional[str] = None

class UserResponse(Struct):
    id: str
    email: str
    name: str
    # Sin password!
```

### ✅ Restricciones de modelo y reglas de negocio

```python
# Restricciones de campos: Annotated/Meta; invariantes: __post_init__
class User(Struct):
    email: str

# ✅ Validar en service
@injectable
class UserService:
    def create(self, data: UserCreate):
        if not self._is_valid_email(data.email):
            raise HTTPException(422, "Invalid email format")
```

---

## 🔐 Security

### ✅ Crear dependencias reutilizables

```python
# shared/dependencies.py
async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> User:
    user = decode_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

async def get_admin_user(
    user: User = Depends(get_current_user)
) -> User:
    if "admin" not in user.roles:
        raise HTTPException(403, "Admin required")
    return user
```

### ✅ Usar en controllers

```python
@app.get("/admin")
def admin_panel(user: User = Depends(get_admin_user)):
    return {"admin": user.name}
```

---

## ⚠️ Error Handling

### ✅ Usar excepciones descriptivas

```python
# shared/exceptions.py
class NotFoundError(HTTPException):
    def __init__(self, resource: str, id: str):
        super().__init__(404, f"{resource} '{id}' not found")

class ConflictError(HTTPException):
    def __init__(self, message: str):
        super().__init__(409, message)
```

### ✅ Custom exception handlers

```python
@app.exception_handler(ConflictError)
def handle_conflict(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
```

---

## ⚡ Performance

### ✅ Usar @injectable (singleton) para objetos pesados

```python
@injectable
class HeavyMLModel:
    def __init__(self):
        self.model = load_model()  # Solo una vez
```

### ✅ Background tasks para tareas breves dentro del proceso

```python
@app.post("/process")
def process(background_tasks: BackgroundTasks):
    background_tasks.add_task(record_metrics)
    return {"status": "processing"}
```

### ✅ Cache para operaciones costosas

```python
@app.get("/expensive")
@cache(TTL=300)
def expensive_operation():
    return compute_something()
```

---

## 🧪 Testing

### ✅ Usar dependency_overrides

```python
def test_with_mock():
    app.dependency_overrides[RealDB] = MockDB
    client = TachyonTestClient(app)
    # ...
    app.dependency_overrides.clear()
```

### ✅ Fixtures reutilizables

```python
# conftest.py
@pytest.fixture
def client():
    return TachyonTestClient(app)

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test_token"}
```

### ✅ Test por capas

```python
# Unit: solo service
def test_user_service():
    repo = MockRepository()
    service = UserService(repo)
    result = service.create(data)
    assert result.id is not None

# Integration: API completa
def test_create_user_api(client):
    response = client.post("/users", json={"email": "ada@example.com", "password": "password123"})
    assert response.status_code == 200
```

---

## 📁 Estructura de Proyecto

### ✅ Recomendada

```
my-api/
├── app.py                  # Entry point (mínimo)
├── config.py               # Settings
├── modules/
│   ├── __init__.py
│   ├── users/              # Feature module
│   └── products/
├── shared/
│   ├── exceptions.py
│   ├── dependencies.py
│   └── middleware.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
└── pyproject.toml
```

### ❌ Evitar

```
my-api/
├── main.py      # 2000 líneas de código
├── models.py    # Todos los modelos juntos
├── routes.py    # Todas las rutas juntas
└── utils.py     # Cajón de sastre
```

---

## ⚡ Production Performance

### ✅ Medir opciones disponibles de servidor

```bash
tachyon run app:app --prod --workers 4
```

El CLI detecta uvloop/httptools opcionales; uvloop requiere una plataforma compatible. Ajustar workers con mediciones del deployment.

- `uvloop`: event loop opcional; medir con el workload y versión desplegados
- `httptools`: parser HTTP opcional; comparar con h11 en el deployment real
- `--workers N`: multiple processes for CPU-bound workloads

### ✅ Install Cython extensions

```bash
pip install tachyon-api
# Para compilar un checkout: seguir docs/16-cython-build.md
```

1.4.0 publica wheels nativos macOS ARM64 para CPython 3.10–3.13 y un wheel portable para el fallback Python; [fast] no recompila un wheel instalado. Los builds de fuente usan Cython y requieren compilador; el fallback portable se solicita con TACHYON_SKIP_CYTHON=1 al construir.

### ✅ Elegir scope según el lifetime

`@injectable` crea su singleton de forma lazy en el primer uso. `Depends(factory)` se cachea por request. Elegir scope según lifetime: un singleton solo puede capturar clases singleton y debe soportar concurrencia desde varios threads. No usarlo para estado por usuario.

### ✅ Elegir el modelo de respuesta según su contrato

```python
class UserResponse(Struct):
    id: int
    name: str

@app.get("/users/{id}", response_model=UserResponse)
def get_user(id: int) -> UserResponse:
    return UserResponse(id=id, name="Alice")  # response_model revalida el JSON
```

Struct se serializa con msgspec. Sin response_model, los dicts JSON simples van directamente a orjson; no requieren un paso Python intermedio. Los hooks intervienen para tipos no nativos. Comparar shapes equivalentes antes de recomendar uno por rendimiento.

### ✅ Minimize middleware

Each middleware adds overhead to every request. Register only what you need:

```python
# Only add what you actually need
app.add_middleware(CORSMiddleware, allow_origins=["*"])  # if you need CORS
# Skip LoggerMiddleware in high-throughput production
```

---

## 📋 Checklist

- [ ] Controllers solo manejan HTTP
- [ ] Services contienen lógica de negocio
- [ ] Repositories abstraen acceso a datos
- [ ] DTOs separados (Create, Update, Response)
- [ ] Dependencies inyectadas, no instanciadas
- [ ] Excepciones descriptivas
- [ ] Tests por capas
- [ ] Cache donde aplique
- [ ] Background tasks breves; cola externa para tareas largas o persistentes
- [ ] Medir uvloop/httptools si están disponibles en la plataforma
- [ ] Verificar wheel o build según la guía de Cython

---

## 🎯 Resumen

| Práctica | Beneficio |
|----------|-----------|
| Clean Architecture | Mantenibilidad |
| @injectable | Singleton, testeable |
| DTOs separados | Seguridad, claridad |
| Excepciones custom | Mejor DX |
| dependency_overrides | Testing fácil |
| Cache | Performance |
| Background tasks | Respuestas rápidas |

BackgroundTasks se espera después del envío y antes del cleanup; no aporta persistencia ni un límite propio de concurrencia. Medir saturación antes de usarlo. Las restricciones de campos y `__post_init__` complementan las reglas de negocio en services.
