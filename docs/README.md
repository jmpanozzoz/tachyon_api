# 📚 Tachyon API Documentation

> **Tachyon** - A lightweight, high-performance web framework inspired by FastAPI

## 🚀 Quick Navigation

### Getting Started
- [01. Getting Started](./01-getting-started.md) - Instalación y primer proyecto
- [02. Architecture](./02-architecture.md) - Arquitectura Clean y estructura de proyecto

### Core Concepts
- [03. Dependency Injection](./03-dependency-injection.md) - Sistema de DI con `@injectable`
- [04. Parameters](./04-parameters.md) - Path, Query, Body, Header, Cookie, Form, File
- [05. Validation](./05-validation.md) - Validación con `Struct` (msgspec)

### Features
- [06. Security](./06-security.md) - Autenticación (Bearer, Basic, OAuth2, API Keys)
- [07. Caching](./07-caching.md) - Sistema de cache con decorador `@cache`
- [08. Lifecycle Events](./08-lifecycle.md) - Startup/Shutdown y lifespan
- [09. Background Tasks](./09-background-tasks.md) - Tareas en segundo plano
- [10. WebSockets](./10-websockets.md) - Comunicación en tiempo real

### Development
- [11. Testing](./11-testing.md) - Testing con `TachyonTestClient`
- [12. CLI Tools](./12-cli.md) - Herramientas de línea de comandos

### Advanced
- [13. Request Lifecycle](./13-request-lifecycle.md) - Ciclo de vida de una request
- [14. Migration from FastAPI](./14-migration-fastapi.md) - Guía de migración
- [15. Best Practices](./15-best-practices.md) - Buenas prácticas
- [16. Cython Build](./16-cython-build.md) - Compilar el hot path `[fast]`

---

## 🎯 Why Tachyon?

| Feature | Tachyon | FastAPI |
|---------|---------|---------|
| **Serialization** | msgspec + orjson | pydantic |
| **Performance** | ⚡ ~5.5x throughput on the published benchmarks | Fast |
| **Routing** | Radix trie O(k), Cython-compiled | Regex scan O(N) |
| **Bundle Size** | 4 core deps | ~15 deps |
| **DI scopes** | 3 (singleton / request / transient) | 1 |
| **Learning Curve** | Easy (FastAPI-like decorators) | Easy |
| **Type Safety** | Full (msgspec Struct) | Full (Pydantic) |
| **OpenAPI** | Automatic (incl. `List[Struct]`, multipart) | Automatic |

## 📦 Installation

```bash
pip install tachyon-api
```

## 🏃 Quick Start

```python
from tachyon_api import Tachyon, Struct, Body

app = Tachyon()

class User(Struct):
    name: str
    email: str

@app.get("/")
def hello():
    return {"message": "Hello, Tachyon!"}

@app.post("/users")
def create_user(user: User = Body(...)):
    return {"created": user.name}
```

```bash
uvicorn app:app --reload
```

Visit: http://localhost:8000/docs

---

## 📖 Version

Current: **1.2.x** — see [CHANGELOG](../CHANGELOG.md) for full history.

## 📄 License

GPL-3.0-or-later
