# 🚀 Tachyon API

![Version](https://img.shields.io/pypi/v/tachyon-api.svg)
![Python](https://img.shields.io/badge/python-3.10--3.13-brightgreen.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-orange.svg)

**A lightweight, high-performance API framework for Python with the elegance of FastAPI and the speed of light.**

Tachyon API combines decorator-based routing, msgspec validation, and ASGI integration on Starlette. Endpoint metadata is prepared at registration to reduce request-time introspection.

[1.4.3 on PyPI](https://pypi.org/project/tachyon-api/1.4.3/) provides one portable Python wheel and one source distribution for Python 3.10–3.13. This release was validated locally on macOS ARM64; Linux and Windows execution remain unverified for 1.4.3. See [release validation](docs/audits/1.4.3/README.md) and the [release notes](https://github.com/jmpanozzoz/tachyon_api/releases/tag/v1.4.3). The [1.4.0 native release record](docs/audits/1.4.0/LOCAL_RELEASE.md) remains historical evidence.

[Source repository](https://github.com/jmpanozzoz/tachyon_api) · [Documentation](docs/README.md).

**1.4.3 uses a single Python implementation**, portable packaging and a corrected orjson minimum. The deprecated `[fast]` extra remains installable as an empty alias. Published older artifacts remain unchanged.

**1.4.3** shares middleware across protocols, protects documentation routes,
centralizes body limits and removes duplicate response/DI work. Its measured
DI operation count improves on one cached graph; no general speedup is claimed.
The [version-bound website evidence](docs/release-evidence.json) is generated
from recorded audits during release preparation. See [the changelog](CHANGELOG.md).

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
pip install tachyon-api==1.4.3
# Testing helpers: pip install "tachyon-api[test]"
tachyon run                 # reload on; optional uvloop/httptools detected, served at :8000
```

📖 **Docs:** http://localhost:8000/docs

---

## ⚡ Performance and builds

Tachyon prepares endpoint metadata at registration. Starting with
1.4.1, its own package uses one Python implementation and no Cython build.
The deprecated `[fast]` extra remains accepted as an empty compatibility alias.
Third-party native libraries retain their own platform requirements.

Performance depends on workload and deployment. See [the measured assessment](docs/quality/framework-review.md)
and [benchmark methodology](benchmark/README.md); no universal multiplier is promised.
See [portable builds and upgrades](docs/16-cython-build.md) and
[local release checks](docs/quality/local-release.md) before upgrading old native or editable installs.

## ✨ Features

| Category | Features |
|----------|----------|
| **Core** | Decorators API, Routers, Middlewares, ASGI compatible |
| **Parameters** | Path, Query, Body (`items: list[Model] = Body()`), Header, Cookie, Form, File; `alias=` only on Header/Cookie/Form/File |
| **Validation** | msgspec Struct (ultra-fast), automatic 422 errors, configurable body size limit (default 2 MiB) |
| **DI** | `@injectable` (3 scopes: singleton / **request** / **transient**), `Depends()` (sync + async), circular dep detection |
| **Security** | HTTPBearer, HTTPBasic, OAuth2, API Keys (Header / Query / Cookie), `SecurityHeadersMiddleware` (X-Frame-Options, CSP, HSTS, …) |
| **Async** | Background Tasks (failures logged, not silenced), WebSockets with **typed path params + DI** |
| **Performance** | orjson serialization, `@cache` decorator, endpoint metadata prepared at registration |
| **Docs** | OpenAPI 3.0 (incl. `List[Struct]` arrays + `multipart/form-data`), Scalar UI, Swagger, ReDoc (XSS-safe HTML generation) |
| **CLI** | Project scaffolding, code generation, linting, AI-agent skill installer |
| **Testing** | `TachyonTestClient` (sync), `create_client()` (async, full httpx kwargs), `dependency_overrides` |
| **Architecture** | Atomic SRP modules across `app/`, `processing/`, `responses/`, `openapi/`, `security/` — one Python implementation |

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
| [Portable builds](./docs/16-cython-build.md) | Python packaging and upgrade from native 1.4.0 installations |

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
Tachyon.__call__ → MiddlewareStack → HTTPDispatcher → TachyonDispatcher
  → route guards → ParameterProcessor → DependencyResolver
  → ResponseProcessor → request-owned ASGI response messages
```

WebSocket and lifespan scopes share that same user middleware chain, then
delegate to Starlette's stack. `scope["app"]` remains Tachyon for every protocol.
Middleware runs in registration order and is constructed once per chain generation;
adding middleware invalidates the chain for subsequent scopes. Registration prepares signatures, converters
and decoders. Trie matching prefers complete static matches and may explore
alternative branches when a static prefix reaches a dead end. Error responses
are created per call; immutable payload bytes and bounded header tables may be
shared. Response messages and mutable headers belong to each send.

The hot path uses one Python implementation since 1.4.1.
The build guide explains upgrades from old native installations and checks for
residual binaries.

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
    async def join(self, ws, room_key: str):
        await ws.accept()

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
cd my_api

# Start development server (optional uvloop + httptools detected, reload on)
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
