# 🚀 Tachyon API

![Version](https://img.shields.io/badge/version-0.7.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-orange.svg)
![Tests](https://img.shields.io/badge/tests-235%20passed-brightgreen.svg)
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
def create_user(user: User = Body(...)):
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

## ✨ Features

| Category | Features |
|----------|----------|
| **Core** | Decorators API, Routers, Middlewares, ASGI compatible |
| **Parameters** | Path, Query, Body, Header, Cookie, Form, File |
| **Validation** | msgspec Struct (ultra-fast), automatic 422 errors |
| **DI** | `@injectable` (implicit), `Depends()` (explicit) |
| **Security** | HTTPBearer, HTTPBasic, OAuth2, API Keys |
| **Async** | Background Tasks, WebSockets |
| **Performance** | orjson serialization, @cache decorator |
| **Docs** | OpenAPI 3.0, Scalar UI, Swagger, ReDoc |
| **CLI** | Project scaffolding, code generation, linting |
| **Testing** | TachyonTestClient, dependency_overrides |

---

## 📚 Documentation

Complete documentation is available in the [`docs/`](./docs/) folder:

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
# Create new project
tachyon new my-api

# Generate module
tachyon generate service users --crud

# Code quality
tachyon lint all
```

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
| **Serialization** | msgspec + orjson | pydantic |
| **Performance** | ⚡⚡⚡ Ultra-fast | ⚡ Fast |
| **Bundle Size** | Minimal | Larger |
| **Learning Curve** | Easy (FastAPI-like) | Easy |
| **Type Safety** | Full | Full |

---

## 📝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest tests/ -v`)
4. Commit your changes (`git commit -m 'Add some amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

---

## 📜 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

---

## 🔮 What's Next

See [CHANGELOG.md](./CHANGELOG.md) for version history.

Upcoming features:
- Response streaming
- GraphQL support
- More deployment guides
- Performance benchmarks

---

*Built with 💜 by developers, for developers*
