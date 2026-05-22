# 🚀 Tachyon API

![Version](https://img.shields.io/badge/version-1.2.x-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-orange.svg)
![Tests](https://img.shields.io/badge/tests-366%20passed-brightgreen.svg)
![Status](https://img.shields.io/badge/status-stable-brightgreen.svg)

**A lightweight, high-performance API framework for Python with the elegance of FastAPI and the speed of light.**

Tachyon API combines the intuitive decorator-based syntax you love with minimal dependencies and maximal performance. Built with Test-Driven Development from the ground up, it offers a cleaner, faster alternative with full ASGI compatibility.

## 🚀 Quick Start

```python
from tachyon_api import Tachyon, Struct, Body, Query

app = Tachyon()

class User(Struct):
    name: str
    email: str

@app.get("/")
def hello():
    return {"message": "Tachyon is running at lightspeed!"}

@app.post("/users")
def create_user(user: User = Body()):
    return {"created": user.name}

@app.get("/search")
def search(q: str = Query(...), limit: int = Query(10)):
    return {"query": q, "limit": limit}
```

```bash
pip install tachyon-api
uvicorn app:app --reload
```

📖 **Docs:** http://localhost:8000/docs

---

## ⚡ Performance

Benchmarked against **FastAPI 0.136.1 (Pydantic v2)** · 1 worker · 100 concurrent connections · uvloop + httptools · Cython extensions compiled

| Scenario | FastAPI | Tachyon | Speedup |
|---|---:|---:|---:|
| Hello World | 10,378 req/s | **49,521 req/s** | **4.77x** |
| Path + query params | 7,294 req/s | **37,991 req/s** | **5.21x** |
| Body validation (Struct) | 8,533 req/s | **41,507 req/s** | **4.86x** |
| Nested body (complex Struct) | 8,205 req/s | **40,816 req/s** | **4.97x** |
| Response model serialization | 6,766 req/s | **47,777 req/s** | **7.06x** |
| Header param + auth | 8,705 req/s | **46,013 req/s** | **5.29x** |
| Dependency injection | 6,491 req/s | **46,940 req/s** | **7.23x** |
| Multiple query params | 6,325 req/s | **34,481 req/s** | **5.45x** |
| **Total throughput** | **62,697 req/s** | **345,046 req/s** | **5.50x** |

**Latency:** ~2.3ms (Tachyon) vs ~13ms (FastAPI) on average.

> Benchmark code in [`benchmark/`](./benchmark/). Run with `bash benchmark/run_benchmark.sh`.

### Optional: Cython compilation

Install with Cython extensions for additional speedup on the request hot path:

```bash
pip install tachyon-api[fast]          # installs cython dependency
python setup.py build_ext --inplace    # compile extensions (required step)
```

> **Note:** `pip install tachyon-api[fast]` installs the `cython` package but does **not**
> auto-compile the extensions. Run `python setup.py build_ext --inplace` manually after install.
> Falls back to pure Python automatically when `.so` is not present — no code changes needed.
> Numbers above reflect the compiled version.

#### What `[fast]` actually buys you (compiled vs pure-Python)

Same code, same workload — the only difference is whether the 27 Cython `.so`
extensions are loaded.  Measured on the same FastAPI benchmark scenarios:

| Scenario | Compiled | Pure-Python | Δ |
|---|---:|---:|---:|
| Hello World | 49,972 req/s | 48,188 req/s | +3.7% |
| Path + query params | 37,282 req/s | 32,244 req/s | **+15.6%** |
| Body — simple Struct | 40,671 req/s | 35,987 req/s | **+13.0%** |
| Body — nested Struct | 40,225 req/s | 34,853 req/s | **+15.4%** |
| Response model | 47,314 req/s | 40,212 req/s | **+17.7%** |
| Header param + auth | 45,426 req/s | 39,901 req/s | **+13.8%** |
| **Dependency injection** | 46,249 req/s | 38,685 req/s | **+19.6%** |
| Multiple query params | 33,832 req/s | 29,924 req/s | **+13.1%** |
| **TOTAL** | **340,971 req/s** | **299,994 req/s** | **+13.7%** |

The biggest wins concentrate on endpoints that do real framework work — DI
resolution (+19.6%), response model serialization (+17.7%), and parameter
validation (+13–15%).  Hello-world barely moves (+3.7%) because the framework
is already a tiny slice of that request — there's no overhead left to compress.

If you're shipping APIs with DI, validation, and response models, the `[fast]`
extra is worth the extra `build_ext` step.  If you're running a thin proxy or
your bottleneck is downstream I/O, the pure-Python fallback is fine.

### Why is Tachyon faster?

- **Radix trie routing** — O(k) path matching vs Starlette's O(N×regex) scan; trie compiled to C
- **Middleware bypass** — HTTP requests skip Starlette's `ServerErrorMiddleware` and `ExceptionMiddleware` entirely; exceptions handled directly in each closure
- **Endpoint pre-compilation** — `inspect.signature()`, `isinstance` chains, type resolution, and `msgspec.Decoder` creation run once at startup, not per request
- **No-Request fast path** — endpoints with no parameters skip `Request()` creation and call the ASGI handler directly
- **msgspec** — validation and deserialization in C, 5–10x faster than Pydantic
- **Direct serialization** — `Struct` responses use `msgspec.json.encode()` directly (no Python intermediate step)
- **Pre-built ASGI dicts** — response send payloads constructed once in `__init__`, not recreated per request
- **No middleware bloat** — Tachyon mounts only what you register; FastAPI adds ~15 middlewares by default

---

## ✨ Features

| Category | Features |
|----------|----------|
| **Core** | Decorators API, Routers, Middlewares, ASGI compatible |
| **Parameters** | Path, Query, Body (incl. `Body(List[Struct])`), Header, Cookie, Form, File (all with `alias=`) |
| **Validation** | msgspec Struct (ultra-fast), automatic 422 errors, configurable body size limit (default 2 MB) |
| **DI** | `@injectable` (3 scopes: singleton / **request** / **transient**), `Depends()` (sync + async), circular dep detection |
| **Security** | HTTPBearer, HTTPBasic, OAuth2, API Keys (Header / Query / Cookie), `SecurityHeadersMiddleware` (X-Frame-Options, CSP, HSTS, …) |
| **Async** | Background Tasks (failures logged, not silenced), WebSockets with **typed path params + DI** |
| **Performance** | orjson serialization, `@cache` decorator, endpoint pre-compilation, optional Cython hot-path |
| **Docs** | OpenAPI 3.0 (incl. `List[Struct]` arrays + `multipart/form-data`), Scalar UI, Swagger, ReDoc (XSS-safe HTML generation) |
| **CLI** | Project scaffolding, code generation, linting, AI-agent skill installer |
| **Testing** | `TachyonTestClient` (sync), `create_client()` (async, full httpx kwargs), `dependency_overrides` |
| **Architecture** | 63 atomic SRP modules across `app/`, `processing/`, `responses/`, `openapi/`, `security/` (v1.2.x refactor) |

---

## 📚 Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](./docs/01-getting-started.md) | Installation and first project |
| [Architecture](./docs/02-architecture.md) | Clean architecture patterns |
| [Dependency Injection](./docs/03-dependency-injection.md) | `@injectable` and `Depends()` |
| [Parameters](./docs/04-parameters.md) | Path, Query, Body, Header, Cookie, Form, File |
| [Validation](./docs/05-validation.md) | msgspec Struct validation |
| [Security](./docs/06-security.md) | JWT, Basic, OAuth2, API Keys |
| [Caching](./docs/07-caching.md) | `@cache` decorator |
| [Lifecycle Events](./docs/08-lifecycle.md) | Startup/Shutdown |
| [Background Tasks](./docs/09-background-tasks.md) | Async task processing |
| [WebSockets](./docs/10-websockets.md) | Real-time communication |
| [Testing](./docs/11-testing.md) | TachyonTestClient |
| [CLI Tools](./docs/12-cli.md) | Scaffolding and generation |
| [Request Lifecycle](./docs/13-request-lifecycle.md) | How requests are processed |
| [Migration from FastAPI](./docs/14-migration-fastapi.md) | Migration guide |
| [Best Practices](./docs/15-best-practices.md) | Recommended patterns |
| [Cython Build](./docs/16-cython-build.md) | Compiling `[fast]` extensions |

---

## 🏦 Example: KYC Demo API

A complete example demonstrating all Tachyon features is available in [`example/`](./example/):

```bash
cd example
pip install -r requirements.txt
uvicorn example.app:app --reload
```

The KYC Demo exercises every v1.2.x feature:
- 🔐 JWT Authentication + API Keys
- 👤 Customer CRUD + bulk endpoint (`Body(List[Struct])`)
- 📋 KYC Verification with Background Tasks
- 📁 Document Uploads (`multipart/form-data`)
- 🌐 WebSocket — legacy plain-string + modern DI-injected with `room_id: uuid.UUID`
- 💉 DI scopes — `singleton` (services), `request` (correlation context), `transient` (ID generator)
- 🛡️ Security headers + opt-in CORS allow-list
- 🚨 Custom exception handler for the `KYCException` hierarchy
- 🧪 17 tests (`pytest example/tests/`), including async tests via `create_client`

**Demo credentials:** `demo@example.com` / `demo123`

👉 See [example/README.md](./example/README.md) for full details.

---

## 🔌 Core Dependencies

| Package | Purpose |
|---------|---------|
| `starlette` | ASGI framework |
| `msgspec` | Ultra-fast validation/serialization |
| `orjson` | High-performance JSON |
| `uvicorn` | ASGI server |

---

## 🏛️ Architecture

Tachyon's request hot path is a thin chain of composed collaborators — every
piece is single-responsibility and ready for Cython compilation:

```
client
  │
  ├─→ Tachyon.__call__ (ASGI entry — sets scope["app"])
  │     │
  │     ├─→ ASGIEntry         lazy build of HTTP app
  │     │
  │     ├─→ HTTPDispatcher    HTTP → trie  ·  WS/lifespan → Starlette
  │     │
  │     ├─→ MiddlewareStack   user-registered middlewares (CORS, Security…)
  │     │
  │     └─→ TachyonDispatcher (Cython cdef)  ← radix trie match O(k)
  │           │
  │           ├─→ _ASGIHandler (no-param fast path, 2 sends only)
  │           │
  │           └─→ handler closure
  │                 ├─→ ParameterPipeline → 10 atomic extractors
  │                 │     (body / query / query-list / header / cookie / form / file / path)
  │                 ├─→ DependencyResolver → OverrideLookup / ScopeCache /
  │                 │                        ClassFactory / CallableFactory
  │                 ├─→ ResponseProcessor (msgspec encode if Struct)
  │                 └─→ ExceptionTable (walks subclass handlers)
  │
  └─→ TachyonJSONResponse | TachyonBytesResponse | _InternalErrorResponse
        (pre-built ASGI dicts, zero extra allocations per response)
```

The v1.2.x SRP refactor decomposed 1,753 monolithic lines into 63 atomic modules
with `__slots__` and full type hints — direct `cdef class` candidates.

👉 [Full architecture documentation](./docs/02-architecture.md)

---

## 💉 Dependency Injection

```python
from tachyon_api import injectable, Depends

@injectable                       # singleton (default) — one per app
class DB:
    def __init__(self):
        self.pool = "..."

@injectable(scope="request")      # one per HTTP request
class RequestContext:
    def __init__(self):
        import uuid
        self.correlation_id = str(uuid.uuid4())

@injectable(scope="transient")    # new instance every time it's injected
class IdGenerator:
    def __init__(self):
        self._seq = 0

@app.get("/users/{id}")
def get_user(id: str, db: DB = Depends(), ctx: RequestContext = Depends()):
    return {"id": id, "trace": ctx.correlation_id}
```

👉 [Full DI documentation](./docs/03-dependency-injection.md)

---

## 🔐 Security

```python
from tachyon_api.security import HTTPBearer, OAuth2PasswordBearer

bearer = HTTPBearer()

@app.get("/protected")
async def protected(credentials = Depends(bearer)):
    return {"token": credentials.credentials}
```

👉 [Full Security documentation](./docs/06-security.md)

---

## ⚡ Background Tasks

```python
from tachyon_api.background import BackgroundTasks

@app.post("/notify")
def notify(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_email, "user@example.com")
    return {"status": "queued"}
```

👉 [Full Background Tasks documentation](./docs/09-background-tasks.md)

---

## 🌐 WebSockets

```python
import uuid
from tachyon_api import injectable, Depends

@injectable
class RoomBroadcaster:
    async def join(self, ws, room_key: str): ...

@app.websocket("/ws/rooms/{room_id}")           # typed UUID path param
async def room(
    websocket,
    room_id: uuid.UUID,                          # auto-converted; 1008 on mismatch
    broadcaster: RoomBroadcaster = Depends(),    # @injectable DI in WS
):
    await broadcaster.join(websocket, str(room_id))
    while True:
        await websocket.send_json({"room": str(room_id)})
```

👉 [Full WebSockets documentation](./docs/10-websockets.md)

---

## 🔧 CLI Tools

```bash
# Create project (generates .env.example, config.py with dotenv, clean arch)
tachyon new my-api

# Start development server (uvloop + httptools auto-detected, reload on)
tachyon run

# List all registered routes
tachyon routes

# Generate a full CRUD module
tachyon g service users --crud

# Generate an ASGI middleware skeleton
tachyon g middleware auth

# Code quality
tachyon lint all
```

**Name validation:** hyphens auto-converted to underscores (`my-api` → `my_api`), Python keywords rejected with a clear error.

### AI Agent Integration

Teach your AI coding assistant (Claude Code, Cursor, Copilot, OpenCode, Codex) how to write correct Tachyon code:

```bash
tachyon install-skill              # generates context files for all tools
tachyon install-skill --cursor     # only .cursorrules
tachyon install-skill --claude     # only CLAUDE.md
tachyon install-skill --copilot    # only .github/copilot-instructions.md
```

Installs knowledge about `Body()` requirement, `Struct` vs BaseModel, DI patterns, CLI commands, and anti-patterns. Safe to run multiple times.

👉 [Full CLI documentation](./docs/12-cli.md)

---

## 🧪 Testing

```python
# Sync — Starlette TestClient compatible
from tachyon_api.testing import TachyonTestClient

def test_hello():
    client = TachyonTestClient(app)
    assert client.get("/").status_code == 200


# Async — httpx.AsyncClient over ASGI transport
import pytest
from tachyon_api.testing import create_client

@pytest.mark.asyncio
async def test_hello_async():
    async with create_client(app, headers={"X-Trace": "abc"}) as client:
        response = await client.get("/")
        assert response.status_code == 200
```

```bash
pytest tests/ -v
```

👉 [Full Testing documentation](./docs/11-testing.md)

---

## 📊 Why Tachyon?

| Feature | Tachyon | FastAPI |
|---------|---------|---------|
| **Throughput** | ~336k req/s total | ~60k req/s total |
| **Latency** | ~2.1ms avg | ~14ms avg |
| **Routing** | Radix trie O(k) | Regex scan O(N) |
| **Serialization** | msgspec + orjson | Pydantic v2 |
| **Request compilation** | Once at startup | Per request |
| **Middleware overhead** | User-only stack | +2 auto middleware layers |
| **Bundle size** | Minimal (4 deps) | Larger (~15 deps) |
| **Learning curve** | Easy (FastAPI-like) | Easy |
| **Type safety** | Full (msgspec Struct) | Full (Pydantic) |

---

## 📝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest tests/ -v`)
4. Commit your changes
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

---

## 📜 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

---

## 🔮 What's Next

See [CHANGELOG.md](./CHANGELOG.md) for version history.

Upcoming:
- Response streaming
- GraphQL support
- Multi-worker benchmarks

---

*Built with 💜 by developers, for developers*
