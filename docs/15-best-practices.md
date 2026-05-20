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
def create_user(user: UserCreate):
    # ❌ Validación de negocio aquí
    if "@" not in user.email:
        raise HTTPException(400, "Invalid email")
    
    # ❌ Acceso a DB aquí
    db.execute("INSERT INTO users ...")
```

### ✅ Mejor

```python
@app.post("/users")
def create_user(user: UserCreate, service: UserService = Depends()):
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

### ✅ Validaciones en Service, no en Struct

```python
# ❌ Struct no soporta validators
class User(Struct):
    email: str  # No puedo validar formato aquí

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
@app.exception_handler(ValidationError)
def handle_validation(request, exc):
    return JSONResponse(
        status_code=422,
        content={"errors": exc.errors}
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

### ✅ Background tasks para trabajo pesado

```python
@app.post("/process")
def process(background_tasks: BackgroundTasks):
    background_tasks.add_task(heavy_processing)
    return {"status": "processing"}
```

### ✅ Cache para operaciones costosas

```python
@app.get("/expensive")
@cache(ttl=300)
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
    response = client.post("/users", json={...})
    assert response.status_code == 201
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

### ✅ Use uvloop and httptools

```bash
uvicorn app:app --loop uvloop --http httptools --workers 4
```

- `uvloop`: Cython-based event loop, ~20% faster than asyncio
- `httptools`: C-based HTTP parser, faster than h11
- `--workers N`: multiple processes for CPU-bound workloads

### ✅ Install Cython extensions

```bash
pip install tachyon-api[fast]
python setup.py build_ext --inplace
```

Compiles the radix trie router and parameter processor to C. Pure Python fallback if not compiled.

### ✅ Prefer `@injectable` over `Depends(factory)`

`@injectable` creates a singleton once at startup. `Depends(factory)` creates a new instance
per request unless you add `@lru_cache`. Use `@injectable` for stateless services.

### ✅ Return `Struct` from endpoints instead of plain dicts

```python
class UserResponse(Struct):
    id: int
    name: str

@app.get("/users/{id}", response_model=UserResponse)
def get_user(id: int) -> UserResponse:
    return UserResponse(id=id, name="Alice")  # uses msgspec.json.encode directly
```

Structs serialize via `msgspec.json.encode()` (pure C), avoiding the Python intermediate step
that dict responses require.

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
- [ ] Background tasks para trabajo pesado
- [ ] uvloop + httptools en producción
- [ ] `pip install tachyon-api[fast]` para extensiones Cython

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
