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

Los middlewares se ejecutan primero, en orden de registro:

```python
app.add_middleware(CORSMiddleware)  # 1ro
app.add_middleware(LoggerMiddleware)  # 2do
app.add_middleware(CustomMiddleware)  # 3ro
```

Cada middleware puede:
- Modificar la request
- Rechazar la request (retornar response)
- Pasar al siguiente middleware

---

## 2️⃣ Route Matching

Tachyon busca el handler que matchea:
- Path: `/users/123`
- Method: `GET`

Si no encuentra: `404 Not Found`

```python
@app.get("/users/{user_id}")  # ← Match!
def get_user(user_id: str):
    ...
```

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

## ⚡ Endpoint Pre-Compilation

A partir de v1.0.0, Tachyon compila cada endpoint **una sola vez al registrarlo**
en `_add_route()`. Esto mueve fuera del hot path:

- `inspect.signature()` — introsección de firma
- `isinstance` chains — detección del tipo de parámetro
- `typing.get_origin/args` — análisis de genéricos (`List[T]`, `Optional[T]`)
- `msgspec.json.Decoder(model)` — creación del decoder de body
- `asyncio.iscoroutinefunction()` — si el endpoint es async
- Resolución de alias para headers/cookies/form/files

En cada request el handler solo recorre un `List[ParamDescriptor]` precompilado.

---

## ⚡ Performance Tips

1. **Dependencies**: Usa `@injectable` (singleton) para clases pesadas — se crean una vez y se reutilizan
2. **Body parsing**: Tachyon respeta el límite `max_body_size` (default 10MB); ajústalo con `Tachyon(max_body_size=...)`
3. **Background tasks**: Mueve trabajo pesado a background para no bloquear la response
4. **Response model**: Evítalo si no necesitas validar el output — la serialización directa es más rápida
5. **Middlewares**: Menos es mejor; cada middleware agrega overhead a todos los requests
6. **Structs sobre dicts**: Retornar un `Struct` usa `msgspec.json.encode()` directo (más rápido que un dict)

---

## 🔗 Próximos Pasos

- [Migration from FastAPI](./14-migration-fastapi.md)
- [Best Practices](./15-best-practices.md)
