# 🚀 Tachyon API

![Version](https://img.shields.io/badge/version-0.5.3-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-orange.svg)
![Status](https://img.shields.io/badge/status-beta-yellow.svg)

**A lightweight, high-performance API framework for Python with the elegance of FastAPI and the speed of light.**

Tachyon API combines the intuitive decorator-based syntax you love with minimal dependencies and maximal performance. Built with Test-Driven Development from the ground up, it offers a cleaner, faster alternative with full ASGI compatibility.

```python
from tachyon_api import Tachyon
from tachyon_api.models import Struct

app = Tachyon()

class User(Struct):
    name: str
    age: int

@app.get("/")
def hello_world():
    return {"message": "Tachyon is running at lightspeed!"}

@app.post("/users")
def create_user(user: User):
    return {"created": user.name}
```

## ✨ Features

- 🔍 **Intuitive API** - Elegant decorator-based routing inspired by FastAPI
- 🧩 **Implicit & Explicit Dependency Injection** - Both supported for maximum flexibility
- 📚 **Automatic OpenAPI Documentation** - With Scalar UI, Swagger UI, and ReDoc support
- 🛠️ **Router System** - Organize your API endpoints with powerful route grouping
- 🧪 **Built with TDD** - Comprehensive test suite ensures stability and correctness
- 🔄 **Middleware Support** - Both class-based and decorator-based approaches
- 🚀 **High-Performance JSON** - Powered by msgspec and orjson for lightning-fast processing
- 🪶 **Minimal Dependencies** - Lean core with only what you really need

## 📦 Installation

Tachyon API is currently in beta. The package will be available on PyPI and Poetry repositories soon!

### From source (Currently the only method)

```bash
git clone https://github.com/jmpanozzoz/tachyon_api.git
cd tachyon-api
pip install -r requirements.txt
```

> **Note:** The `pip install tachyon-api` and `poetry add tachyon-api` commands will be available once the package is published to PyPI.

## 🔍 Key Differences from FastAPI

While inspired by FastAPI's elegant API design, Tachyon API takes a different approach in several key areas:

| Feature | Tachyon API | FastAPI |
|---------|------------|---------|
| **Core Dependencies** | Minimalist: Starlette + msgspec + orjson | Pydantic + multiple dependencies |
| **Validation Engine** | msgspec (faster, lighter) | Pydantic (more features, heavier) |
| **Dependency Injection** | Both implicit and explicit | Primarily explicit |
| **Middleware Approach** | Dual API (class + decorator) | Class-based |
| **Development Approach** | Test-Driven from the start | Feature-driven |
| **Documentation UI** | Scalar UI (default), Swagger, ReDoc | Swagger UI (default), ReDoc |
| **Size** | Lightweight, focused | Comprehensive, full-featured |

## 🧪 Test-Driven Development

Tachyon API is built with TDD principles at its core:

- Every feature starts with a test
- Comprehensive test coverage
- Self-contained test architecture
- Clear test documentation

This ensures stability, maintainability, and prevents regressions as the framework evolves.

## 🔌 Core Dependencies

Tachyon API maintains a minimal, carefully selected set of dependencies:

- **[Starlette](https://www.starlette.io/)**: ASGI framework providing solid foundations
- **[msgspec](https://jcristharif.com/msgspec/)**: Ultra-fast serialization and validation
- **[orjson](https://github.com/ijl/orjson)**: High-performance JSON parser
- **[uvicorn](https://www.uvicorn.org/)**: ASGI server for development and production

These were chosen for their performance, lightweight nature, and focused functionality.

## 💉 Dependency Injection System

Tachyon API offers a flexible dependency injection system:

### Implicit Injection

```python
@injectable
class UserService:
    def __init__(self, repository: UserRepository):  # Auto-injected!
        self.repository = repository

@app.get("/users/{user_id}")
def get_user(user_id: int, service: UserService):  # Auto-injected!
    return service.get_user(user_id)
```

### Explicit Injection

```python
@app.get("/users/{user_id}")
def get_user(user_id: int, service: UserService = Depends()):
    return service.get_user(user_id)
```

## 🔄 Middleware Support

Tachyon API supports middlewares in two elegant ways:

### Class-based Approach

```python
class TimingMiddleware:
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        start_time = time.time()
        await self.app(scope, receive, send)
        print(f"Request took {time.time() - start_time:.4f}s")

app.add_middleware(TimingMiddleware)
```

### Decorator-based Approach

```python
@app.middleware()
async def timing_middleware(scope, receive, send, app):
    start_time = time.time()
    await app(scope, receive, send)
    print(f"Request took {time.time() - start_time:.4f}s")
```

## 📚 Example Application

For a complete example showcasing all features, see the [example directory](./example). It demonstrates:

- Clean architecture with models, services, and repositories
- Router organization
- Middleware implementation
- Dependency injection patterns
- OpenAPI documentation

Run the example with:

```bash
cd example
python app.py
```

Then visit:
- **API**: http://localhost:8000/
- **Documentation**: http://localhost:8000/docs

## 📝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🔮 Roadmap

- [ ] **Exception System**: Standardized exception handling and error responses
- [ ] **Environment Management**: Built-in environment variable handling and uvicorn integration
- [ ] **CLI Tool**: Project scaffolding and service generation
  - Directory structure generation
  - Service and repository templates
  - API endpoint generation
- [ ] **Code Quality Tools**: Ruff integration for linting and formatting
- [ ] **Performance Optimization**: Cython compilation for service layer via CLI
- [ ] **Authentication Middleware**: Built-in auth patterns and middleware
- [ ] **Performance Benchmarks**: Comparisons against other frameworks
- [ ] **More Example Applications**: Demonstrating different use cases
- [ ] **Plugin System**: Extensibility through plugins
- [ ] **Deployment Guides**: Documentation for various deployment scenarios
- [ ] **And much more!**

---

<p align="center">
  <em>Built with 💜 by developers, for developers</em>
</p>
