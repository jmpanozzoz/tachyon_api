# 🏦 KYC Demo API

> A complete example demonstrating all Tachyon features

This example implements a **Know Your Customer (KYC)** verification system that showcases:

## ✨ Features Demonstrated

| Feature | Location | Description |
|---------|----------|-------------|
| **Clean Architecture** | `modules/` | Controller → Service → Repository pattern |
| **Dependency Injection** | `@injectable`, `Depends()` | Automatic DI with type hints |
| **JWT Authentication** | `modules/auth/` | Login, registration, token validation |
| **API Key Auth** | `shared/dependencies.py` | Service-to-service auth |
| **File Uploads** | `modules/documents/` | Document upload with validation |
| **Background Tasks** | `modules/verification/` | Async verification processing |
| **WebSockets** | `app.py` | Real-time status notifications |
| **Caching** | `verification_service.py` | `@cache` decorator usage |
| **Lifecycle Events** | `app.py` | `lifespan` context manager |
| **Custom Exceptions** | `shared/exceptions.py` | Descriptive error handling |
| **Testing Utilities** | `tests/` | `TachyonTestClient`, `dependency_overrides` |

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

# Run the server
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

- All data is stored in-memory (mock databases)
- Verification processing is simulated with random delays
- 90% of verification checks pass (for demo purposes)

## 🔗 Related Documentation

- [Getting Started](../docs/01-getting-started.md)
- [Architecture](../docs/02-architecture.md)
- [Dependency Injection](../docs/03-dependency-injection.md)
- [Security](../docs/06-security.md)
- [Background Tasks](../docs/09-background-tasks.md)
- [WebSockets](../docs/10-websockets.md)
- [Testing](../docs/11-testing.md)
