# 04. Parameters

> Todos los tipos de parámetros soportados por Tachyon

## 📍 Path Parameters

Parámetros en la URL:

```python
from tachyon_api import Tachyon, Path

app = Tachyon()

# Implícito (sin Path())
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}

# Explícito (con Path())
@app.get("/items/{item_id}")
def get_item(item_id: str = Path(..., description="The item ID")):
    return {"item_id": item_id}

# Múltiples path params
@app.get("/users/{user_id}/posts/{post_id}")
def get_post(user_id: int, post_id: int):
    return {"user_id": user_id, "post_id": post_id}
```

---

## ❓ Query Parameters

Parámetros en el query string (`?key=value`):

```python
from tachyon_api import Tachyon, Query
from typing import Optional, List

app = Tachyon()

# Requerido
@app.get("/search")
def search(q: str = Query(...)):
    return {"query": q}

# Opcional con default
@app.get("/items")
def list_items(
    skip: int = Query(0),
    limit: int = Query(10),
    sort: str = Query("id")
):
    return {"skip": skip, "limit": limit, "sort": sort}

# Opcional (None si no se envía)
@app.get("/filter")
def filter_items(category: Optional[str] = Query(None)):
    return {"category": category}

# Lista de valores (?tags=a&tags=b o ?tags=a,b)
@app.get("/tags")
def get_by_tags(tags: List[str] = Query(...)):
    return {"tags": tags}
```

---

## 📦 Body Parameters

Datos JSON en el body:

```python
from tachyon_api import Tachyon, Struct, Body
from typing import Optional

class UserCreate(Struct):
    name: str
    email: str
    age: int = 18

class UserUpdate(Struct):
    name: Optional[str] = None
    email: Optional[str] = None

app = Tachyon()

@app.post("/users")
def create_user(user: UserCreate = Body(...)):
    return {"created": user.name, "email": user.email}

@app.put("/users/{user_id}")
def update_user(user_id: str, data: UserUpdate = Body(...)):
    return {"updated": user_id, "data": data}
```

---

## 📋 Header Parameters

Valores de headers HTTP:

```python
from tachyon_api import Tachyon, Header
from typing import Optional

app = Tachyon()

# Requerido
@app.get("/auth")
def check_auth(authorization: str = Header(...)):
    return {"token": authorization}

# Con alias (nombre diferente)
@app.get("/api")
def api_call(api_key: str = Header(..., alias="X-API-Key")):
    return {"api_key": api_key}

# Opcional
@app.get("/trace")
def trace(trace_id: Optional[str] = Header(None, alias="X-Trace-ID")):
    return {"trace_id": trace_id or "not provided"}

# User-Agent (underscore → hyphen automático)
@app.get("/info")
def info(user_agent: str = Header("unknown")):
    return {"user_agent": user_agent}
```

---

## 🍪 Cookie Parameters

Valores de cookies:

```python
from tachyon_api import Tachyon, Cookie
from typing import Optional

app = Tachyon()

# Requerido
@app.get("/session")
def get_session(session_id: str = Cookie(...)):
    return {"session": session_id}

# Opcional con default
@app.get("/preferences")
def get_prefs(theme: str = Cookie("light")):
    return {"theme": theme}

# Con alias
@app.get("/tracking")
def tracking(tracker: Optional[str] = Cookie(None, alias="_ga")):
    return {"tracker": tracker}
```

---

## 📝 Form Parameters

Datos de formulario (`application/x-www-form-urlencoded`):

```python
from tachyon_api import Tachyon, Form

app = Tachyon()

@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...)
):
    return {"username": username}

@app.post("/contact")
def contact(
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form("")
):
    return {"received": True}
```

---

## 📁 File Uploads

Subida de archivos (`multipart/form-data`):

```python
from tachyon_api import Tachyon, File, Form
from tachyon_api.files import UploadFile
from typing import Optional

app = Tachyon()

# Archivo requerido
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    contents = await file.read()
    return {
        "filename": file.filename,
        "size": len(contents),
        "content_type": file.content_type
    }

# Archivo opcional
@app.post("/profile")
async def update_profile(
    name: str = Form(...),
    avatar: Optional[UploadFile] = File(None)
):
    result = {"name": name}
    if avatar:
        result["avatar"] = avatar.filename
    return result

# Múltiples archivos
@app.post("/gallery")
async def upload_gallery(
    title: str = Form(...),
    images: list[UploadFile] = File(...)
):
    return {
        "title": title,
        "images": [img.filename for img in images]
    }
```

---

## 🔀 Combinando Parámetros

Puedes combinar todos los tipos:

```python
from tachyon_api import Tachyon, Struct, Body, Query, Header, Path
from typing import Optional

class ItemCreate(Struct):
    name: str
    price: float

app = Tachyon()

@app.post("/stores/{store_id}/items")
def create_item(
    # Path
    store_id: str,
    # Query
    notify: bool = Query(False),
    # Header
    authorization: str = Header(...),
    # Body
    item: ItemCreate = Body(...)
):
    return {
        "store": store_id,
        "item": item.name,
        "notify": notify,
        "auth": authorization[:20] + "..."
    }
```

---

## 📋 Resumen

| Tipo | Marker | Ubicación | Ejemplo |
|------|--------|-----------|---------|
| Path | `Path()` | URL | `/users/{id}` |
| Query | `Query()` | Query string | `?page=1` |
| Body | `Body()` | JSON body | `{"name": "..."}` |
| Header | `Header()` | HTTP headers | `Authorization: ...` |
| Cookie | `Cookie()` | Cookies | `session_id=abc` |
| Form | `Form()` | Form data | `username=john` |
| File | `File()` | Multipart | File upload |

---

## 🔗 Próximos Pasos

- [Validation](./05-validation.md) - Validación con Struct
- [Security](./06-security.md) - Headers de autenticación
