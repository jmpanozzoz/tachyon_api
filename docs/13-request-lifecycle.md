# 13. Request Lifecycle

> Cómo Tachyon procesa cada request

## 🔄 Flujo Completo

```
                    ┌─────────────────────────────────────────┐
                    │           INCOMING REQUEST              │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │            MIDDLEWARES                  │
                    │  (CORS, Logger, Custom...)              │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │          ROUTE MATCHING                 │
                    │  Find handler for path + method         │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │       PARAMETER EXTRACTION              │
                    │  Path, Query, Headers, Cookies          │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │        BODY PARSING (if any)            │
                    │  JSON → Struct validation               │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │      DEPENDENCY RESOLUTION              │
                    │  @injectable, Depends(callable)         │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │         ENDPOINT EXECUTION              │
                    │  Your handler function runs             │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │        BACKGROUND TASKS                 │
                    │  Run queued tasks                       │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │       RESPONSE SERIALIZATION            │
                    │  Struct → JSON (orjson)                 │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │            MIDDLEWARES                  │
                    │  (Response processing)                  │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │           SEND RESPONSE                 │
                    └─────────────────────────────────────────┘
```

---

## 1️⃣ Middlewares (Pre-request)

Los middlewares del usuario se ejecutan primero, en orden de registro:

```python
app.add_middleware(CORSMiddleware)   # 1ro
app.add_middleware(LoggerMiddleware) # 2do
app.add_middleware(CustomMiddleware) # 3ro
```

Cada middleware puede modificar, rechazar o pasar la request al siguiente.

> **Nota de rendimiento (Phase 4):** Tachyon construye su propio HTTP stack con solo
> los middlewares del usuario, sin las capas automáticas de Starlette
> (`ServerErrorMiddleware` + `ExceptionMiddleware`). Las excepciones ya se manejan
> dentro de cada handler closure con `try/except`. Esto ahorra ~1.5–2µs por request.
> WebSockets y lifespan sí usan el stack completo de Starlette.

---

## 2️⃣ Route Matching — Radix Trie (O(k))

Tachyon usa un radix trie para resolver paths en O(k) donde k = número de segmentos del path (típicamente 2–5). Esto reemplaza el escaneo lineal O(N×regex) de Starlette.

```
GET /users/123
  → root → "users" → {user_id=123} → handler_get_user
  (cada segmento es un dict lookup O(1))
```

Si el path no existe → `404 Not Found`  
Si el path existe pero no el método → `405 Method Not Allowed`

```python
@app.get("/users/{user_id}")  # Registrado en el trie al arrancar
def get_user(user_id: str):
    ...
```

Las rutas se registran una sola vez en `_add_route()`. En cada request, el trie resuelve en microsegundos sin importar cuántas rutas tenga la app.

---

## 3️⃣ Parameter Extraction

Tachyon inspecciona la firma del handler:

```python
@app.get("/items/{item_id}")
def get_item(
    item_id: str,                      # Path param
    q: str = Query(...),               # Query param
    auth: str = Header(...),           # Header
    session: str = Cookie("default"),  # Cookie
):
```

### Orden de extracción:
1. Path parameters (`{param}` en URL)
2. Query parameters (`?key=value`)
3. Headers
4. Cookies
5. Form/File (si aplica)

---

## 4️⃣ Body Parsing

Si hay `Body()`, Tachyon:
1. Lee el body JSON
2. Decodifica con msgspec
3. Valida contra el Struct

```python
class UserCreate(Struct):
    name: str
    email: str

@app.post("/users")
def create_user(user: UserCreate = Body(...)):
    # user ya está validado
    ...
```

Si falla la validación: `422 Validation Error`

---

## 5️⃣ Dependency Resolution

Tachyon resuelve dependencias en orden:

```python
@app.get("/data")
def get_data(
    request: Request,              # 1. Inyectar Request
    bg: BackgroundTasks,           # 2. Inyectar BackgroundTasks
    db: Database = Depends(),      # 3. Resolver @injectable
    user: dict = Depends(get_user) # 4. Ejecutar callable
):
```

### Algoritmo:
1. Check `dependency_overrides` (testing)
2. Check cache (singleton para @injectable)
3. Resolver dependencias anidadas (recursivo)
4. Instanciar/ejecutar

---

## 6️⃣ Endpoint Execution

Se llama al handler con todos los params inyectados:

```python
# Sync
result = handler(**kwargs)

# Async
result = await handler(**kwargs)
```

### Excepciones:
- `HTTPException` → Response con status code
- Custom exception → Check `exception_handlers`
- Unhandled → `500 Internal Server Error`

---

## 7️⃣ Background Tasks

Después del endpoint, pero antes de responder:

```python
if background_tasks:
    await background_tasks.run_tasks()
```

Las tareas se ejecutan en orden.

---

## 8️⃣ Response Serialization

Tachyon serializa el resultado por el camino más eficiente según el tipo:

```python
# Struct → msgspec.json.encode() directo (C puro, sin paso intermedio)
if isinstance(result, Struct):
    return TachyonBytesResponse(msgspec.json.encode(result))

# Dict → orjson.dumps() (serialización C)
return TachyonJSONResponse(result)
```

`TachyonJSONResponse` bypasea el `__init__` estándar de Starlette para evitar la
construcción de `MutableHeaders` (~0.96µs ahorrados por response).

Si hay `response_model`, valida con `msgspec.convert()` antes de serializar.

---

## 9️⃣ Middlewares (Post-response)

Los middlewares procesan la response en orden inverso:

```python
# Request:  CORS → Logger → Custom → Handler
# Response: Handler → Custom → Logger → CORS
```

---

## ⚠️ Error Handling

```
                    ┌─────────────────────────────────────────┐
                    │            EXCEPTION RAISED             │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │         Is HTTPException?               │
                    │  YES → Check exception_handlers         │
                    │        → Default: {"detail": ...}       │
                    └─────────────────┬───────────────────────┘
                                      │ NO
                    ┌─────────────────▼───────────────────────┐
                    │    Check custom exception_handlers      │
                    │    for this exception type              │
                    └─────────────────┬───────────────────────┘
                                      │ Not found
                    ┌─────────────────▼───────────────────────┐
                    │       500 Internal Server Error         │
                    └─────────────────────────────────────────┘
```

---

## ⚡ Optimizaciones del hot path

### Endpoint Pre-Compilation (v1.0.0)
Tachyon compila cada endpoint **una sola vez al registrarlo** en `_add_route()`. Esto mueve fuera del hot path:

- `inspect.signature()`, `iscoroutinefunction()`, `isinstance` chains
- `typing.get_origin/args` — genéricos (`List[T]`, `Optional[T]`)
- `msgspec.json.Decoder(model)` — decoder de body
- Resolución de aliases para headers/cookies/form/files
- `has_params` y `has_callable_deps` — flags para fast-paths en cada request

En request time, el handler recorre una `List[ParamDescriptor]` precompilada con tipos C-level.

### Middleware bypass (Phase 4)
Para requests HTTP, Tachyon saltea `ServerErrorMiddleware` y `ExceptionMiddleware` de
Starlette. Solo aplica los middlewares del usuario. Ahorra ~1.5–2µs por request.

### Cython extensions (optional — `pip install tachyon-api[fast]`)
Con extensiones compiladas:
- `ParamDescriptor` y `CompiledEndpoint` → `cdef class` (struct C, acceso a campos directo)
- `routing/trie.pyx` → trie en C, match loop sin overhead Python por segmento
- `KIND_*` constants → enteros (comparación C de una instrucción)
- Sync helpers → `cdef` functions (sin frame Python por llamada)
- `process_parameters` path+query: **2.32µs → 0.82µs** (-65%) con Cython

### No-Request fast path (Phase 5)
Endpoints sin parámetros ni dependencias callable se registran como `_ASGIHandler`:
el dispatcher llama `handler(scope, receive, send)` directamente, sin crear el objeto
`Request(scope, receive, send)`. Una allocación menos por request.

### Pre-built ASGI response dicts (Phase 2)
`TachyonJSONResponse` y `TachyonBytesResponse` pre-construyen los dicts `http.response.start`
y `http.response.body` en `__init__`. El `__call__` solo hace 2 `await send(prebuilt_dict)`.

---

## ⚡ Performance Tips

1. **Dependencies**: Usa `@injectable` (singleton) para clases pesadas — se crean una vez y se reutilizan
2. **Body parsing**: Tachyon respeta el límite `max_body_size` (default 10MB); ajústalo con `Tachyon(max_body_size=...)`
3. **Background tasks**: Mueve trabajo pesado a background para no bloquear la response
4. **Response model**: Evítalo si no necesitas validar el output — la serialización directa es más rápida
5. **Middlewares**: Menos es mejor; cada middleware agrega overhead a todos los requests
6. **Structs sobre dicts**: Retornar un `Struct` usa `msgspec.json.encode()` directo (más rápido que un dict)
7. **Compilación Cython**: `pip install tachyon-api[fast]` para -11% en el hot path Python

---

## 🔗 Próximos Pasos

- [Migration from FastAPI](./14-migration-fastapi.md)
- [Best Practices](./15-best-practices.md)
