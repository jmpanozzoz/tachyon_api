# 🏦 KYC Demo API

> A complete example demonstrating all Tachyon v1.2.x features

This example implements a **Know Your Customer (KYC)** verification system on
top of Tachyon v1.2.x. It exercises every feature added through the v1.2.x
cycle so users coming from FastAPI can map idioms 1:1.

## ✨ Features Demonstrated

| Feature | Location | Description |
|---------|----------|-------------|
| **Clean Architecture** | `modules/` | Controller → Service → Repository pattern |
| **Dependency Injection (singleton)** | `@injectable`, `Depends()` | The default scope — one instance per app |
| **DI scope: request** ⭐ v1.2.0 | `shared/request_context.py` | `@injectable(scope="request")` — fresh per HTTP request |
| **DI scope: transient** ⭐ v1.2.0 | `shared/id_generator.py` | `@injectable(scope="transient")` — fresh per injection point |
| **JWT Authentication** | `modules/auth/` | Login, registration, token validation |
| **API Key Auth** | `shared/dependencies.py` | Service-to-service auth |
| **File Uploads (multipart)** | `modules/documents/` | `Form()` + `File()` → `multipart/form-data` in OpenAPI |
| **Bulk request body** ⭐ v1.2.0 | `customers_controller.bulk_create_customers` | Nested `List[Struct]` inside a Struct body |
| **`List[Struct]` response model** ⭐ v1.2.0 | `customers_controller.list_recent_customers` | `response_model=List[CustomerResponse]` → array schema |
| **Background Tasks** | `modules/verification/` | Async verification processing |
| **WebSockets — DI + typed path** ⭐ v1.2.0 | `modules/admin/admin_ws.py` | `room_id: uuid.UUID` + `Depends(AdminBroadcaster)` |
| **WebSockets — legacy plain path** | `app.py` | Original customer-notification channel kept for compat |
| **Security headers** ⭐ v1.2.0 | `app.py` | `SecurityHeadersMiddleware` registered explicitly |
| **CORS opt-in** ⭐ v1.2.0 | `app.py` | Explicit `allow_origins` list (no more wildcard default) |
| **Custom exception handler** | `app.py` | `@app.exception_handler(HTTPException)` with isinstance dispatch |
| **Caching** | `verification_service.py` | `@cache` decorator usage |
| **Lifecycle Events** | `app.py` | `lifespan` context manager |
| **Custom Exceptions** | `shared/exceptions.py` | Descriptive error hierarchy |
| **Testing — sync** | `tests/conftest.py` | `TachyonTestClient`, `dependency_overrides` |
| **Testing — async** ⭐ v1.2.0 | `tests/test_async_client.py` | `tachyon_api.testing.create_client` with httpx kwargs |

⭐ = new or revised in Tachyon v1.2.0. Click through to the source for usage.

> **Known limitations (v1.2.83 audit findings):**
> - `Body(List[Struct])` directly fails at runtime — the OpenAPI spec is
>   generated correctly but the msgspec decoder is only configured for direct
>   Struct subclasses.  Workaround used here: wrap in a Struct (see
>   `BulkCreateRequest` in `customers_dto.py`).
> - `@app.exception_handler(KYCException)` is not invoked — Tachyon's dispatch
>   currently only consults `HTTPException` as the catch-all for HTTPException
>   subclasses.  Workaround: register for `HTTPException` and dispatch by
>   `isinstance` inside the handler (see `app.py`).
> - `pytest example/tests/` collection fails on pytest 8.x + pytest-asyncio
>   0.23.x (`'Package' object has no attribute 'obj'`).  All tests in this
>   directory are correct in content; the collection issue is structural.

Both runtime gaps will be addressed in the v1.2.9 Cython sprint.

## 📁 Project Structure

```
example/
├── app.py                      # Main application
├── config.py                   # Configuration
├── requirements.txt            # Dependencies
│
├── modules/                    # Feature modules
│   ├── auth/                   # Authentication
│   │   ├── auth_controller.py
│   │   ├── auth_service.py
│   │   └── auth_dto.py
│   │
│   ├── customers/              # Customer management
│   │   ├── customers_controller.py
│   │   ├── customers_service.py
│   │   ├── customers_repository.py
│   │   └── customers_dto.py
│   │
│   ├── verification/           # KYC verification
│   │   ├── verification_controller.py
│   │   ├── verification_service.py
│   │   ├── verification_repository.py
│   │   └── verification_dto.py
│   │
│   └── documents/              # Document uploads
│       ├── documents_controller.py
│       ├── documents_service.py
│       └── documents_dto.py
│
├── shared/                     # Shared utilities
│   ├── dependencies.py         # Auth dependencies
│   ├── exceptions.py           # Custom exceptions
│   └── websocket_manager.py    # WebSocket connections
│
└── tests/                      # Tests
    ├── conftest.py             # Fixtures
    ├── test_auth.py
    ├── test_customers.py
    └── test_verification.py
```

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: install Cython extensions for extra speed
pip install tachyon-api[fast]

# Run the server (from project root)
uvicorn example.app:app --reload --loop uvloop

# Open docs
open http://localhost:8000/docs
```

## 🔐 Demo Credentials

| Email | Password | Role |
|-------|----------|------|
| `demo@example.com` | `demo123` | user |
| `admin@example.com` | `admin123` | admin |

## 📋 API Flow

### 1. Authenticate

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "demo123"}'
```

### 2. Create Customer Profile

```bash
curl -X POST http://localhost:8000/customers/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com"
  }'
```

### 3. Upload Documents

```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "customer_id=<customer_id>" \
  -F "document_type=passport" \
  -F "file=@passport.jpg"
```

### 4. Start Verification

```bash
curl -X POST http://localhost:8000/verification/start \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "<customer_id>"}'
```

### 5. Connect to WebSocket for Updates

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/notifications/<customer_id>");

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Status update:", data);
};
```

## 🧪 Running Tests

```bash
# From project root
pytest example/tests/ -v

# With coverage
pytest example/tests/ --cov=example
```

## 🔧 Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Environment name |
| `DEBUG` | `true` | Enable debug mode |
| `SECRET_KEY` | (generated) | JWT signing key |

## 📝 Notes

- All data is stored in-memory (mock databases) — replace with real DB for production
- Verification processing is simulated with random delays (~1–3s)
- 90% of verification checks pass (for demo purposes)
- Add `--loop uvloop --http httptools` to the uvicorn command for production performance

## 🔗 Related Documentation

- [Getting Started](../docs/01-getting-started.md)
- [Architecture](../docs/02-architecture.md)
- [Dependency Injection](../docs/03-dependency-injection.md)
- [Security](../docs/06-security.md)
- [Background Tasks](../docs/09-background-tasks.md)
- [WebSockets](../docs/10-websockets.md)
- [Testing](../docs/11-testing.md)
