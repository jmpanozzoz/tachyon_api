# 🚀 Tachyon API

![Version](https://img.shields.io/badge/version-0.5.7-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-orange.svg)
![Status](https://img.shields.io/badge/status-stable-brightgreen.svg)

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

- 🔍 Intuitive API (decorators) and minimal core
- 🧩 Implicit & explicit DI
- 📚 OpenAPI with Scalar, Swagger, ReDoc
- 🛠️ Router system
- 🔄 Middlewares (class + decorator)
- 🧠 Cache decorator with TTL (in-memory, Redis, Memcached)
- 🚀 High-performance JSON (msgspec + orjson)
- 🧾 Unified error format (422/500) + global exception handler (500)
- 🧰 Default JSON response (TachyonJSONResponse)
- 🔒 End-to-end safety: request Body validation + typed response_model
- 📘 Deep OpenAPI schemas: nested Structs, Optional/List (nullable/array), formats (uuid, date-time)

## 🧪 Test-Driven Development

Tachyon API is built with TDD principles at its core. The test suite covers routing, DI, params, body validation, responses, OpenAPI generation, caching, and example flows.

## 🔌 Core Dependencies

- Starlette (ASGI)
- msgspec (validation/serialization)
- orjson (fast JSON)
- uvicorn (server)

## 💉 Dependency Injection System

- Implicit injection: annotate with registered types
- Explicit injection: Depends() for clarity and control

## 🔄 Middleware Support

- Built-in: CORSMiddleware and LoggerMiddleware
- Use app.add_middleware(...) or @app.middleware()

## ⚡ Cache with TTL

- @cache(TTL=...) on routes and functions
- Per-app config and pluggable backends (InMemory, Redis, Memcached)

## 📚 Example Application

The example demonstrates clean architecture, routers, middlewares, caching, end-to-end safety, and global exception handling:

- /orjson-demo: default JSON powered by orjson
- /api/v1/users/e2e: Body + response_model, unified errors and deep OpenAPI schemas
- /error-demo: triggers an unhandled exception to showcase the global handler (structured 500)

Run the example:

```
cd example
python app.py
```

Docs at /docs (Scalar), /swagger, /redoc.

## ✅ Response models, OpenAPI params, and deep schemas

- Response models: set response_model=YourStruct to validate/convert outputs via msgspec before serializing.
- Parameter schemas: Optional[T] → nullable: true; List[T] → type: array with items.
- Deep schemas: nested Struct components, Optional/List items, and formats (uuid, date-time) are generated and referenced in components.

## 🧾 Default JSON response and unified error format

- Default response: TachyonJSONResponse serializes complex types (UUID/date/datetime, Struct) via orjson and centralized encoders.
- 422 Validation: { success: false, error, code: VALIDATION_ERROR, [errors] }.
- 500 Response model: { success: false, error: "Response validation error: ...", detail, code: RESPONSE_VALIDATION_ERROR }.
- 500 Unhandled exceptions (global): { success: false, error: "Internal Server Error", code: INTERNAL_SERVER_ERROR }.

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

- Exception system and global handlers
- CLI, scaffolding, and code quality tooling
- Authentication middleware and benchmarks
- More examples and deployment guides

---

*Built with 💜 by developers, for developers*
