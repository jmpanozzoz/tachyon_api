# 12. CLI Tools

> Command-line toolkit for Tachyon projects — scaffolding, code generation, development server, and code quality.

## Installation

The CLI is included with `tachyon-api`:

```bash
pip install tachyon-api
tachyon --help
```

---

## Command Overview

| Command | Description |
|---------|-------------|
| `tachyon new <name>` | Create a new project |
| `tachyon run [app]` | Start the development / production server |
| `tachyon routes [app]` | List all registered routes |
| `tachyon g service <name>` | Generate a full module (controller + service + repo + dto + tests) |
| `tachyon g controller <name>` | Generate a controller only |
| `tachyon g repository <name>` | Generate a repository only |
| `tachyon g dto <name>` | Generate a DTO file only |
| `tachyon g middleware <name>` | Generate an ASGI middleware skeleton |
| `tachyon openapi export <app>` | Export OpenAPI schema to JSON |
| `tachyon openapi validate <file>` | Validate an OpenAPI schema file |
| `tachyon lint check` | Check code quality (ruff) |
| `tachyon lint fix` | Auto-fix linting issues |
| `tachyon lint format` | Format code |
| `tachyon lint all` | Lint + format in one step |
| `tachyon version` | Show installed version |

---

## 🏗️ tachyon new

Create a new Tachyon project with clean architecture.

```bash
tachyon new my-api
tachyon new my-api --path ./projects
```

**Name rules:** hyphens are converted to underscores (`my-api` → `my_api`), Python keywords are rejected.

### Generated structure

```
my-api/
├── .env.example            # Environment variable template — copy to .env
├── app.py                  # Application entry point
├── config.py               # Settings (reads from .env via python-dotenv)
├── requirements.txt        # Dependencies
├── modules/                # Feature modules (one per domain)
│   └── __init__.py
├── shared/                 # Shared utilities
│   ├── __init__.py
│   ├── exceptions.py       # Typed HTTP exceptions (NotFoundError, etc.)
│   └── dependencies.py     # Shared DI dependencies
└── tests/
    ├── __init__.py
    └── conftest.py         # Pytest fixtures (async client pre-configured)
```

### Next steps after `tachyon new`

```bash
cd my-api
cp .env.example .env          # configure your environment
pip install -r requirements.txt
tachyon run                   # starts at http://localhost:8000
```

---

## ▶ tachyon run

Start the server with sensible defaults — wraps uvicorn with auto-detected uvloop and httptools.

```bash
# Development (auto-reload, single worker)
tachyon run

# Custom app / port
tachyon run app:app --port 9000

# Production (no reload, multiple workers)
tachyon run --prod --workers 4

# Custom host
tachyon run --host 127.0.0.1

# TachyonServer — enables F12b direct transport writes
tachyon run --tachyon-server
```

| Flag | Default | Description |
|------|---------|-------------|
| `app` | `app:app` | Module:attribute path to the ASGI app |
| `--host` / `-h` | `0.0.0.0` | Bind host |
| `--port` / `-p` | `8000` | Bind port |
| `--reload / --no-reload` | `True` | Auto-reload on file changes |
| `--workers` / `-w` | `1` | Worker processes |
| `--prod` | `False` | Production mode — disables reload, sets workers to 4 if unset |
| `--tachyon-server` | `False` | Use `TachyonHTTPProtocol` for direct socket writes |

> **Note:** `--prod` overrides `--reload` regardless of flags order.

---

## 📋 tachyon routes

Inspect all registered routes without starting the server.

```bash
tachyon routes          # reads app:app in current directory
tachyon routes myapp:app
```

Output example:

```
Registered routes:
  ────────────────────────────────────────
  METHOD    PATH                    NAME
  ────────────────────────────────────────
  GET       /                       root
  GET       /health                 health
  GET       /users                  list_users
  GET       /users/{id}             get_user
  POST      /users                  create_user
  PUT       /users/{id}             update_user
  DELETE    /users/{id}             delete_user
  ────────────────────────────────────────
  7 route(s) total.
```

Methods are colour-coded: GET=green, POST=blue, PUT=yellow, PATCH=cyan, DELETE=red.

---

## 🔧 tachyon generate (alias: g)

Generate code components. All names accept hyphens (auto-converted to snake_case).

### Full service module

```bash
tachyon g service users
tachyon generate service users   # same thing
```

Generates:

```
modules/users/
├── __init__.py
├── users_controller.py     # Router with endpoints
├── users_service.py        # Business logic (@injectable)
├── users_repository.py     # Data access layer
├── users_dto.py            # Struct models
└── tests/
    └── test_users_service.py
```

Then register the router in `app.py`:

```python
from modules.users import router as users_router
app.include_router(users_router)
```

### With CRUD endpoints (`--crud`)

```bash
tachyon g service products --crud
```

Adds full CRUD to the controller and service:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/products` | List with `skip` + `limit` pagination |
| `GET` | `/products/{id}` | Get one by ID |
| `POST` | `/products` | Create (body: `ProductCreate`) |
| `PUT` | `/products/{id}` | Update (body: `ProductUpdate`) |
| `DELETE` | `/products/{id}` | Delete |

### Options

```bash
tachyon g service auth --no-tests    # skip test file
tachyon g service users --path src/modules   # custom output path
```

### Individual components

```bash
tachyon g controller orders    # only the controller file
tachyon g repository orders    # only the repository file
tachyon g repo orders          # alias for repository
tachyon g dto orders           # only the DTO file
```

---

## 🔒 tachyon generate middleware

Generate an ASGI middleware skeleton.

```bash
tachyon g middleware auth
tachyon g middleware rate_limit --path ./middlewares
```

Generates `middlewares/auth_middleware.py`:

```python
class AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        response = await self.process(request)
        if response is not None:
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    async def process(self, request: Request) -> Response | None:
        # Return a Response to short-circuit, or None to continue
        return None
```

Register in `app.py`:

```python
from middlewares.auth_middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)
```

---

## 📄 tachyon openapi

### Export schema

```bash
tachyon openapi export app:app               # stdout
tachyon openapi export app:app -o schema.json
tachyon openapi export app:app -o schema.json --indent 4
```

### Validate schema

```bash
tachyon openapi validate schema.json
```

```
✅ Schema is valid!
   OpenAPI version: 3.0.0
   Title: My API
   Paths: 12
```

---

## 🔍 tachyon lint

Wrapper over [ruff](https://docs.astral.sh/ruff/) for code quality.

```bash
tachyon lint check              # check all
tachyon lint check ./modules    # specific path
tachyon lint check --fix        # auto-fix
tachyon lint check --watch      # watch mode

tachyon lint fix                # fix all
tachyon lint fix --unsafe       # include unsafe fixes

tachyon lint format             # format
tachyon lint format --check     # dry-run (no writes)
tachyon lint format --diff      # show diff

tachyon lint all                # lint + format together
tachyon lint all --no-fix       # report only
```

### Recommended `ruff.toml`

```toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
```

---

## ⚙️ Environment & configuration

`tachyon new` generates a `.env.example` alongside `config.py`:

```bash
# .env.example
APP_NAME=Tachyon API
VERSION=0.1.0
DEBUG=true
HOST=0.0.0.0
PORT=8000
# DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

```bash
cp .env.example .env   # create your local env file
```

`config.py` loads `.env` automatically via `python-dotenv` (gracefully skipped in production where env vars are set directly):

```python
from config import settings
print(settings.APP_NAME)  # reads from .env or environment
```

---

## 🔗 Related

- [Architecture](./02-architecture.md) — clean architecture patterns
- [Dependency Injection](./03-dependency-injection.md) — `@injectable` and `Depends()`
- [Testing](./11-testing.md) — `TachyonTestClient` and fixtures
