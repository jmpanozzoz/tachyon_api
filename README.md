# 🚀 Tachyon API

![Version](https://img.shields.io/badge/version-1.4.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10--3.13-brightgreen.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-orange.svg)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)

**A lightweight, high-performance API framework for Python with the elegance of FastAPI and the speed of light.**

Tachyon API combines decorator-based routing, msgspec validation, and ASGI integration on Starlette. Endpoint metadata is prepared at registration to reduce request-time introspection.

1.4.0 is validated through the [local release process](docs/quality/local-release.md). Native wheels are built and tested on macOS ARM64; the portable wheel supplies the Python fallback for platforms without a matching native wheel. Other operating systems are not validated by the local Mac runs.

The [1.4 migration guide](docs/17-migration-1.4.md) describes execution, body limits, resource lifetime, schema support and packaging changes.

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
# Testing helpers: pip install "tachyon-api[test]"
tachyon run                 # uvloop + httptools + reload, served at :8000
```

📖 **Docs:** http://localhost:8000/docs

---

## ⚡ Performance and builds

Tachyon precompiles endpoint metadata and provides optional native Cython
extensions. Performance depends on the application, workload, and deployment.
Benchmarks must compare equivalent handler execution and dependency scopes. See
[`benchmark/`](./benchmark/) for the benchmark harness and its limitations.

The planned native wheel matrix targets CPython 3.10–3.13 on Linux x86_64/aarch64,
macOS arm64, and Windows AMD64. On other platforms pip builds from source,
requiring a C compiler. Compilation errors fail the build explicitly.
For a portable pure Python installation from source:

```bash
TACHYON_SKIP_CYTHON=1 pip install --no-binary=tachyon-api tachyon-api
```

The environment variable controls builds; it does not disable native modules
already installed. `[fast]` supplies Cython for development; isolated source
builds already install Cython as a build dependency. See the
[Cython build guide](./docs/16-cython-build.md).

## ✨ Features

| Category | Features |
|----------|----------|
| **Core** | Decorators API, Routers, Middlewares, ASGI compatible |
| **Parameters** | Path, Query, Body (`items: list[Model] = Body()`), Header, Cookie, Form, File; `alias=` only on Header/Cookie/Form/File |
| **Validation** | msgspec Struct (ultra-fast), automatic 422 errors, configurable body size limit (default 2 MiB) |
| **DI** | `@injectable` (3 scopes: singleton / **request** / **transient**), `Depends()` (sync + async), circular dep detection |
| **Security** | HTTPBearer, HTTPBasic, OAuth2, API Keys (Header / Query / Cookie), `SecurityHeadersMiddleware` (X-Frame-Options, CSP, HSTS, …) |
| **Async** | Background Tasks (failures logged, not silenced), WebSockets with **typed path params + DI** |
| **Performance** | orjson serialization, `@cache` decorator, endpoint pre-compilation, optional Cython extensions |
| **Docs** | OpenAPI 3.0 (incl. `List[Struct]` arrays + `multipart/form-data`), Scalar UI, Swagger, ReDoc (XSS-safe HTML generation) |
| **CLI** | Project scaffolding, code generation, linting, AI-agent skill installer |
| **Testing** | `TachyonTestClient` (sync), `create_client()` (async, full httpx kwargs), `dependency_overrides` |
| **Architecture** | Atomic SRP modules across `app/`, `processing/`, `responses/`, `openapi/`, `security/` — optional native modules for the hot path |

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
| [Cython Build](./docs/16-cython-build.md) | Precompiled wheels, source builds, and the `.py`/`.pyx` fallback model |

---

## 🏦 Example: KYC Demo API

An example demonstrating selected Tachyon features is available in [`example/`](./example/):

```bash
# From the repository root
pip install -r example/requirements.txt
tachyon run example.app:app
```

The KYC Demo exercises:
- 🔐 JWT Authentication + API Keys
- 👤 Customer CRUD and list response models
- 📋 KYC Verification with Background Tasks
- 🌐 Customer notification WebSocket with a string customer ID
- 💉 DI scopes — `singleton` services and `request` correlation context
- 🛡️ Security headers + opt-in CORS allow-list
- 🚨 Custom exception handler for the `KYCException` hierarchy
- 🧪 HTTP, async-client, WebSocket and lifespan tests (`pytest example/tests/`)

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

The normal HTTP request path is composed from these collaborators:

```text
Tachyon.__call__ → ASGIEntry → MiddlewareStack → TachyonDispatcher
  → route guards → ParameterProcessor → DependencyResolver
  → ResponseProcessor → request-owned ASGI response messages
```

WebSocket and lifespan scopes delegate to Starlette. `HTTPDispatcher` supports
the Starlette compatibility flow. Registration prepares signatures, converters
and decoders. Trie matching prefers complete static matches and may explore
alternative branches when a static prefix reaches a dead end. Error responses
are created per call; immutable payload bytes and bounded header tables may be
shared. Response messages and mutable headers belong to each send.

The hot path has Python implementations with optional native Cython siblings.
Python prefers native modules when installed. See the build guide for explicit
pure Python builds.

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
tachyon g service user --crud

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
pytest tests/ example/tests/ -v
```

👉 [Full Testing documentation](./docs/11-testing.md)

---

## 📝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest tests/ example/tests/ -v`)
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
- A dedicated streaming API; Starlette `StreamingResponse` already passes through the ASGI response path
- GraphQL support
- Multi-worker benchmarks
- Benchmark suite vs Litestar / BlackSheep / Robyn
- SQLAlchemy async integration guide

---

*Built with 💜 by developers, for developers*
