# 06. Security

> Autenticación y autorización en Tachyon

## 🔐 Security Schemes Disponibles

| Scheme | Uso | Header |
|--------|-----|--------|
| HTTPBearer | JWT tokens | `Authorization: Bearer <token>` |
| HTTPBasic | Usuario/password | `Authorization: Basic <base64>` |
| OAuth2PasswordBearer | Extracción de token Bearer | `Authorization: Bearer <token>` |
| APIKeyHeader | API Key en header | `X-API-Key: <key>` |
| APIKeyQuery | API Key en query | `?api_key=<key>` |
| APIKeyCookie | API Key en cookie | Cookie: `session=<key>` |

---

## 🎫 HTTPBearer (JWT)

HTTPBearer extrae un token Bearer; la aplicación debe validar firma, expiración y permisos antes de autenticar. Este ejemplo usa un token fijo de demostración:

```python
from tachyon_api import Tachyon, Depends, HTTPException
from tachyon_api.security import HTTPBearer, HTTPAuthorizationCredentials

app = Tachyon()
security = HTTPBearer()

def decode_token(token: str) -> dict:
    """Tu lógica de decodificación JWT."""
    # Ejemplo simplificado
    if token == "valid_token":
        return {"user_id": "123", "name": "John"}
    return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    user = decode_token(credentials.credentials)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

@app.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return user

@app.get("/profile")
def get_profile(user: dict = Depends(get_current_user)):
    return {"profile": user["name"]}
```

### Request:
```bash
curl -H "Authorization: Bearer valid_token" http://localhost:8000/me
```

---

## 👤 HTTPBasic

Para autenticación básica usuario/contraseña:

```python
from tachyon_api import Tachyon, Depends, HTTPException
from tachyon_api.security import HTTPBasic, HTTPBasicCredentials
import secrets

app = Tachyon()
security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "secret")
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"}
        )
    return credentials.username

@app.get("/admin")
def admin_panel(username: str = Depends(verify_credentials)):
    return {"message": f"Welcome, {username}!"}
```

### Request:
```bash
curl -u admin:secret http://localhost:8000/admin
```

---

## 🔑 OAuth2PasswordBearer

Extracción Bearer y un endpoint de login de demostración. No implementa por sí solo un servidor OAuth2 ni valida JWT:

```python
from tachyon_api import Tachyon, Depends, HTTPException, Form
from tachyon_api.security import OAuth2PasswordBearer

app = Tachyon()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# Endpoint de login
@app.post("/token")
def login(username: str = Form(...), password: str = Form(...)):
    # Validar credenciales
    if username == "user" and password == "pass":
        return {"access_token": "fake_token", "token_type": "bearer"}
    raise HTTPException(401, "Invalid credentials")

# Endpoint protegido
@app.get("/users/me")
def get_current_user(token: str = Depends(oauth2_scheme)):
    # Decodificar token
    if token != "fake_token":
        raise HTTPException(401, "Invalid token")
    return {"username": "user", "token": token}
```

---

## 🗝️ API Keys

### En Header:

```python
from tachyon_api import Tachyon, Depends, HTTPException
from tachyon_api.security import APIKeyHeader

app = Tachyon()
api_key_header = APIKeyHeader(name="X-API-Key")

VALID_API_KEYS = {"key123", "key456"}

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key not in VALID_API_KEYS:
        raise HTTPException(403, "Invalid API Key")
    return api_key

@app.get("/api/data")
def get_data(api_key: str = Depends(verify_api_key)):
    return {"data": "secret", "key": api_key}
```

### En Query Parameter:

```python
from tachyon_api.security import APIKeyQuery

api_key_query = APIKeyQuery(name="api_key")

@app.get("/api/v2/data")
def get_data_v2(api_key: str = Depends(api_key_query)):
    return {"data": "from query"}
```

### En Cookie:

```python
from tachyon_api.security import APIKeyCookie

api_key_cookie = APIKeyCookie(name="session_token")

@app.get("/dashboard")
def dashboard(session: str = Depends(api_key_cookie)):
    return {"session": session}
```

---

## 🛡️ Autenticación Opcional

Para endpoints que funcionan con o sin auth:

```python
from tachyon_api import Tachyon, Depends, HTTPException
from tachyon_api.security import HTTPBearer

# Reutiliza decode_token del primer ejemplo.
app = Tachyon()
security = HTTPBearer(auto_error=False)

@app.get("/items")
async def list_items(credentials = Depends(security)):
    if credentials:
        # La presencia del token no autentica: validarlo antes de dar acceso.
        user = decode_token(credentials.credentials)
        if not user:
            raise HTTPException(401, "Invalid token")
        return {"items": ["public", "private"], "user": user["name"]}
    else:
        # Usuario anónimo - solo público
        return {"items": ["public"], "user": "anonymous"}
```

---

## 🎭 Roles y Permisos

```python
from tachyon_api import Depends, HTTPException
from typing import List

def require_roles(*allowed_roles: str):
    """Factory para crear dependency de roles."""
    async def role_checker(user: dict = Depends(get_current_user)):
        user_roles = user.get("roles", [])
        for role in allowed_roles:
            if role in user_roles:
                return user
        raise HTTPException(403, "Insufficient permissions")
    return role_checker

@app.get("/admin")
def admin_only(user: dict = Depends(require_roles("admin"))):
    return {"admin": True}

@app.get("/editor")
def editor_or_admin(user: dict = Depends(require_roles("editor", "admin"))):
    return {"can_edit": True}
```

---

## 📋 Resumen

| Scheme | Import | Uso típico |
|--------|--------|------------|
| `HTTPBearer` | `from tachyon_api.security import HTTPBearer` | JWT, tokens |
| `HTTPBasic` | `from tachyon_api.security import HTTPBasic` | Login simple |
| `OAuth2PasswordBearer` | `from tachyon_api.security import OAuth2PasswordBearer` | OAuth2 |
| `APIKeyHeader` | `from tachyon_api.security import APIKeyHeader` | API keys |
| `APIKeyQuery` | `from tachyon_api.security import APIKeyQuery` | API keys |
| `APIKeyCookie` | `from tachyon_api.security import APIKeyCookie` | Sessions |

---

## 🔗 Próximos Pasos

- [Caching](./07-caching.md) - Sistema de cache
- [Testing](./11-testing.md) - Testear endpoints protegidos

`OAuth2PasswordBearer` extrae credenciales Bearer; no valida JWT ni permisos. `tokenUrl` actualmente no genera `components.securitySchemes` ni `operation.security` en OpenAPI y no configura automáticamente autenticación en la UI.
