# 🚀 Tachyon API

![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-orange.svg)
![Tests](https://img.shields.io/badge/tests-233%20passed-brightgreen.svg)
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
| Hello World | 10,225 req/s | **49,946 req/s** | **4.88x** |
| Path + query params | 7,127 req/s | **37,943 req/s** | **5.32x** |
| Body validation (Struct) | 8,257 req/s | **41,286 req/s** | **5.00x** |
| Nested body (complex Struct) | 7,949 req/s | **40,304 req/s** | **5.07x** |
| Response model serialization | 6,749 req/s | **47,202 req/s** | **6.99x** |
| Header param + auth | 8,648 req/s | **45,531 req/s** | **5.26x** |
| Dependency injection | 6,337 req/s | **46,168 req/s** | **7.28x** |
| Multiple query params | 6,279 req/s | **34,414 req/s** | **5.48x** |
| **Total throughput** | **61,571 req/s** | **342,794 req/s** | **5.57x** |

**Latency:** ~2.4ms (Tachyon) vs ~14ms (FastAPI) on average.

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
> Numbers above reflect the compiled version (~11% faster Python hot path).

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
| **Parameters** | Path, Query, Body, Header, Cookie, Form, File (all with `alias=`) |
| **Validation** | msgspec Struct (ultra-fast), automatic 422 errors, body size limit |
| **DI** | `@injectable` (implicit), `Depends()` (explicit), circular dep detection |
| **Security** | HTTPBearer, HTTPBasic, OAuth2, API Keys |
| **Async** | Background Tasks, WebSockets |
| **Performance** | orjson serialization, `@cache` decorator, endpoint pre-compilation |
| **Docs** | OpenAPI 3.0, Scalar UI, Swagger, ReDoc (XSS-safe HTML generation) |
| **CLI** | Project scaffolding, code generation, linting |
| **Testing** | `TachyonTestClient`, `dependency_overrides` |

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

---

## 🏦 Example: KYC Demo API

A complete example demonstrating all Tachyon features is available in [`example/`](./example/):

```bash
cd example
pip install -r requirements.txt
uvicorn example.app:app --reload
```

The KYC Demo implements:
- 🔐 JWT Authentication
- 👤 Customer CRUD
- 📋 KYC Verification with Background Tasks
- 📁 Document Uploads
- 🌐 WebSocket Notifications
- 🧪 12 Tests with Mocks

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

## 💉 Dependency Injection

```python
from tachyon_api import injectable, Depends

@injectable
class UserService:
    def get_user(self, id: str):
        return {"id": id}

@app.get("/users/{id}")
def get_user(id: str, service: UserService = Depends()):
    return service.get_user(id)
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
@app.websocket("/ws")
async def websocket(ws):
    await ws.accept()
    data = await ws.receive_text()
    await ws.send_text(f"Echo: {data}")
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

👉 [Full CLI documentation](./docs/12-cli.md)

---

## 🧪 Testing

```python
from tachyon_api.testing import TachyonTestClient

def test_hello():
    client = TachyonTestClient(app)
    response = client.get("/")
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
