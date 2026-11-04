# 🏦 KYC Demo API

> A compact example demonstrating selected Tachyon features

This example implements a **Know Your Customer (KYC)** verification system on
top of Tachyon. Tests exercise authentication, customers, verification, async HTTP helpers, notification WebSockets and lifespan startup/shutdown; they do not establish exhaustive endpoint coverage.

## ✨ Features Demonstrated

| Feature | Location | Description |
|---------|----------|-------------|
| **Clean Architecture** | `modules/` | Controller → Service → Repository pattern |
| **Dependency Injection (singleton)** | `@injectable`, `Depends()` | The default scope — one instance per app |
| **DI scope: request** | `shared/request_context.py` | `@injectable(scope="request")` — fresh per HTTP request |
| **JWT Authentication** | `modules/auth/` | Login, registration, token validation |
| **`List[Struct]` response model** | `customers_controller.list_recent_customers` | `response_model=List[CustomerResponse]` → array schema |
| **Background tasks** | `modules/verification/` | Enqueues verification processing after the HTTP response |
| **WebSockets** | `app.py` | Customer-notification channel; tests exercise messages through the notification manager |
| **Security headers** | `app.py` | `SecurityHeadersMiddleware` registered explicitly |
| **CORS opt-in** | `app.py` | Explicit `allow_origins` list (no wildcard default) |
| **Custom exception handler** | `app.py` | `@app.exception_handler(KYCException)` — subclasses of `HTTPException` are dispatched correctly |
| **Caching** | `verification_service.py` | `@cache` decorator usage |
| **Lifecycle Events** | `app.py` | `lifespan` context manager |
| **Custom Exceptions** | `shared/exceptions.py` | Descriptive error hierarchy |
| **Testing — sync** | `tests/conftest.py` | `TachyonTestClient`, `dependency_overrides` |
| **Testing — async** | `tests/test_async_client.py` | `tachyon_api.testing.create_client` with httpx kwargs |

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
│   └── verification/           # KYC verification
│       ├── verification_controller.py
│       ├── verification_service.py
│       ├── verification_repository.py
│       └── verification_dto.py
│
├── shared/                     # Shared utilities
│   ├── dependencies.py         # Auth dependencies
│   ├── exceptions.py           # Custom exceptions
│   ├── request_context.py      # Request-scoped DI showcase
│   └── websocket_manager.py    # WebSocket connections
│
└── tests/                      # Tests
    ├── conftest.py             # Fixtures
    ├── test_async_client.py
    ├── test_auth.py
    ├── test_configuration.py
    ├── test_customers.py
    ├── test_verification.py
    └── test_websocket_lifecycle.py
```

## 🚀 Quick Start

```bash
# From the repository root (the directory containing example/)
pip install -r example/requirements.txt

# Run the server (from project root)
uvicorn example.app:app --reload

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

### 3. Start Verification

```bash
curl -X POST http://localhost:8000/verification/start \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "<customer_id>"}'
```

### 4. Connect to the Notification WebSocket

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
python -m pip install pytest-cov
pytest example/tests/ --cov=example
```

## 🔧 Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Environment name |
| `DEBUG` | `true` in development, `false` otherwise | Enable debug mode |
| `SECRET_KEY` | Random ephemeral key only in development/test | JWT signing key; required in production |

## 📝 Notes

- All data is stored in-memory (mock databases) — replace with real DB for production
- The controller checks `background_tasks is not None` so the first task is enqueued even when the collection is empty. The HTTP regression verifies that the processing worker is awaited with the returned verification ID; test workers replace simulated provider delays. Notification tests send through the manager directly and do not assert a complete random verification job.
- When the simulated processing method is invoked, each check waits 0.5–1.5 seconds; total processing time depends on the number of checks. Tachyon background tasks run after the response is sent and complete before request cleanup.
- Each verification check has a simulated 90% pass probability; this is not a guaranteed aggregate result.
- `--loop uvloop --http httptools` selects optional Uvicorn implementations when installed on a compatible platform; benchmark the application before claiming a speed improvement.

## 🔗 Related Documentation

- [Getting Started](../docs/01-getting-started.md)
- [Architecture](../docs/02-architecture.md)
- [Dependency Injection](../docs/03-dependency-injection.md)
- [Security](../docs/06-security.md)
- [Background Tasks](../docs/09-background-tasks.md)
- [WebSockets](../docs/10-websockets.md)
- [Testing](../docs/11-testing.md)

Production (`ENVIRONMENT=production` or any environment other than development/test) requires a SECRET_KEY of at least 32 characters and rejects known demo placeholders. Development/test generate a random key per Settings instance if missing; restarting invalidates existing tokens. Set an explicit key for stable tokens across workers/restarts. This remains an in-memory demo, not a production KYC service.
