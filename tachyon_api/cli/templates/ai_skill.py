"""
AI skill / rules content for Tachyon API.

This is the canonical knowledge base injected into each AI tool's context file.
"""

# ── Core content (all tools share this) ──────────────────────────────────────

_HEADER = "# Tachyon API — AI Context"

_OVERVIEW = """\
Tachyon API is a high-performance Python web framework with FastAPI-inspired decorator syntax,
built on Starlette + msgspec + orjson. It is NOT a wrapper of FastAPI — it is an
independent implementation with a different internal architecture.

Key differences from FastAPI:
- Uses `msgspec.Struct` instead of Pydantic BaseModel for validation (different API)
- Body parameters REQUIRE `= Body()` marker — not just a type annotation
- `@injectable` for singleton services, `Depends()` for callable/class DI
- `tachyon_api.Struct` is re-exported from msgspec — use it everywhere instead of BaseModel
- Factories accept typed Request/WebSocket, Depends, injectable classes, Python defaults, Header and Query
- Other parameter markers inside factories fail registration; use typed Request for explicit extraction
- Singleton constructors may capture singleton classes only; use request scope for per-user state
- Mutable Struct fields require deliberate sharing; constructors do not validate, response_model does
- OAuth2PasswordBearer extracts tokens without JWT validation or automatic OpenAPI security schemes
- Router uses `app.include_router(router)` just like FastAPI
- Query extraction and type conversion require explicit `Query(default)` markers
"""

_INSTALLATION = """\
## Installation

```bash
pip install tachyon-api
uvicorn app:app --reload --loop uvloop  # or: tachyon run
```
"""

_QUICK_REFERENCE = """\
## Quick Reference

### Imports
```python
from tachyon_api import Tachyon, Struct, Body, Query, Path, Header, Cookie
from tachyon_api import Router, Depends, injectable, HTTPException
from tachyon_api.security import HTTPBearer, OAuth2PasswordBearer
from tachyon_api.background import BackgroundTasks
```

### Basic app
```python
from tachyon_api import Tachyon
app = Tachyon()

@app.get("/")
def root():
    return {"status": "ok"}
```

### Models — use Struct, NOT BaseModel
```python
from tachyon_api import Struct

class User(Struct):
    name: str
    email: str
    age: int = 0  # default values work

class UserResponse(Struct):
    id: str
    name: str
    email: str
```

### Parameters
```python
# Path param (implicit — name must match {path_param} in route)
@app.get("/users/{user_id}")
def get_user(user_id: int):
    ...

# Query param
@app.get("/users")
def list_users(skip: int = Query(0), limit: int = Query(100)):
    ...

# Body — ALWAYS use Body() for POST/PUT/PATCH body params
@app.post("/users")
def create_user(user: User = Body()):  # ← Body() is REQUIRED
    ...

# Header
@app.get("/auth")
def auth(x_api_key: str = Header(...)):
    ...
```

### Dependency Injection
```python
from tachyon_api import injectable, Depends

@injectable
class UserService:
    def get(self, id: str): return {"id": id}

# Implicit (annotated param that's @injectable)
@app.get("/users/{id}")
def get_user(id: str, svc: UserService):  # svc injected automatically
    return svc.get(id)

# Explicit
@app.get("/users/{id}")
def get_user(id: str, svc: UserService = Depends()):
    return svc.get(id)
```

### Routers
```python
from tachyon_api import Router

router = Router(prefix="/users", tags=["Users"])

@router.get("/")
def list_users(): ...

# In app.py
app.include_router(router)
```

### Error handling
```python
from tachyon_api import HTTPException

raise HTTPException(status_code=404, detail="User not found")
raise HTTPException(status_code=422, detail="Validation failed")
```

### Response model
```python
@app.get("/users/{id}", response_model=UserResponse)
def get_user(id: str):
    return UserResponse(id=id, name="Alice", email="alice@example.com")
```
"""

_PATTERNS = """\
## Common Patterns

### CRUD endpoint set
```python
from typing import List
from tachyon_api import Router, Depends, Body, Query
from tachyon_api import injectable, HTTPException, Struct

class Item(Struct):
    name: str
    price: float

class ItemResponse(Struct):
    id: str
    name: str
    price: float

@injectable
class ItemService:
    def __init__(self):
        self._store: dict = {}

    def list(self, skip=0, limit=100):
        return list(self._store.values())[skip:skip+limit]

    def get(self, id: str):
        item = self._store.get(id)
        if not item:
            raise HTTPException(404, "Item not found")
        return item

    def create(self, data: Item) -> dict:
        import uuid, msgspec
        id = str(uuid.uuid4())
        item = {"id": id, **msgspec.structs.asdict(data)}
        self._store[id] = item
        return item

router = Router(prefix="/items", tags=["Items"])

@router.get("/", response_model=List[ItemResponse])
def list_items(skip: int = Query(0), limit: int = Query(100), svc: ItemService = Depends()):
    return svc.list(skip, limit)

@router.get("/{id}", response_model=ItemResponse)
def get_item(id: str, svc: ItemService = Depends()):
    return svc.get(id)

@router.post("/", response_model=ItemResponse)
def create_item(data: Item = Body(), svc: ItemService = Depends()):
    return svc.create(data)
```

### Authentication with Bearer token
```python
from tachyon_api.security import HTTPBearer

bearer = HTTPBearer()

@app.get("/me")
async def me(credentials = Depends(bearer)):
    token = credentials.credentials  # the raw JWT string
    # validate token here
    return {"token": token}
```

### Background tasks
```python
import asyncio
from tachyon_api.background import BackgroundTasks

@app.post("/notify")
async def notify(msg: str = Query(...), bg: BackgroundTasks = None):
    async def send_email():
        await asyncio.sleep(1)
        print(f"Sent: {msg}")
    bg.add_task(send_email)
    return {"queued": True}
```
"""

_ANTIPATTERNS = """\
## Anti-patterns to avoid

```python
# ❌ WRONG — Body param without Body() — fails registration for an unbound required parameter
@app.post("/users")
def create_user(user: User):  # broken
    ...

# ✅ CORRECT
@app.post("/users")
def create_user(user: User = Body()):
    ...

# ❌ WRONG — using Pydantic BaseModel
from pydantic import BaseModel
class User(BaseModel): ...  # won't integrate with Tachyon serialization

# ✅ CORRECT
from tachyon_api import Struct
class User(Struct): ...

# ❌ WRONG — data.__dict__ on a Struct (no __dict__)
item = {"id": id, **data.__dict__}  # AttributeError

# ✅ CORRECT
import msgspec
item = {"id": id, **msgspec.structs.asdict(data)}

# ❌ WRONG — blocking work in an async exception handler
@app.exception_handler(HTTPException)
async def handler(request, exc): time.sleep(1)  # blocks the event loop

# ✅ CORRECT
@app.exception_handler(HTTPException)
async def handler(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=500)
```
"""


def _cli_reference() -> str:
    from typer.main import get_command
    from ..main import app

    root = get_command(app)
    lines = [
        "## CLI Reference",
        "",
        "Registered commands (run with --help for arguments):",
        "",
    ]

    def walk(group, prefix: str) -> None:
        for name, command in sorted(getattr(group, "commands", {}).items()):
            target = f"{prefix} {name}"
            lines.append(
                f"- `{target}` — {(command.help or '').strip().splitlines()[0] if command.help else ''}"
            )
            walk(command, target)

    walk(root, "tachyon")
    return "\n".join(lines)


def _installed_reference() -> str:
    import inspect
    import tachyon_api
    from .service import ServiceTemplates

    lines = ["## Installed public API", ""]
    for name in tachyon_api.__all__:
        value = getattr(tachyon_api, name)
        try:
            signature = str(inspect.signature(value))
        except (TypeError, ValueError):
            signature = ""
        lines.append(f"- `tachyon_api.{name}{signature}`")
    lines += [
        "",
        "## Service template example",
        "",
        "```python",
        ServiceTemplates.controller("example", "Example").strip(),
        "```",
    ]
    return "\n".join(lines)


_FOOTER = """\
---
Full docs: https://github.com/jmpanozzoz/tachyon_api
"""


# ── Tool-specific wrappers ────────────────────────────────────────────────────


def _full_content() -> str:
    return "\n\n".join(
        [
            _HEADER,
            _OVERVIEW.strip(),
            _INSTALLATION.strip(),
            _QUICK_REFERENCE.strip(),
            _PATTERNS.strip(),
            _ANTIPATTERNS.strip(),
            _cli_reference(),
            _installed_reference(),
            _FOOTER.strip(),
        ]
    )


def cursor_rules() -> str:
    """Content for .cursorrules"""
    return f"""\
{_HEADER}

You are an expert Tachyon API developer. Always follow these rules when working
with Tachyon API projects.

{_OVERVIEW.strip()}

{_QUICK_REFERENCE.strip()}

{_ANTIPATTERNS.strip()}

{_cli_reference()}

{_installed_reference()}
"""


def claude_md_snippet() -> str:
    """Snippet to append to CLAUDE.md (or use as standalone)"""
    return f"""\
# Tachyon API — Project Context

This project uses **Tachyon API** — a high-performance FastAPI-alternative framework.

{_OVERVIEW.strip()}

{_QUICK_REFERENCE.strip()}

{_ANTIPATTERNS.strip()}

{_cli_reference()}

{_installed_reference()}
"""


def copilot_instructions() -> str:
    """Content for .github/copilot-instructions.md"""
    return _full_content()


def opencode_rules() -> str:
    """Content for .opencode/rules.md"""
    return _full_content()


def agents_md() -> str:
    """Content for AGENTS.md (generic — works with Codex, Aider, etc.)"""
    return _full_content()
