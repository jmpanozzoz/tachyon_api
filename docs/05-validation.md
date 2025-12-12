# 05. Validation

> Validación automática con msgspec Struct

## 🎯 Struct Basics

Tachyon usa `msgspec.Struct` para definir modelos de datos:

```python
from tachyon_api import Struct
from typing import Optional, List

class User(Struct):
    name: str
    email: str
    age: int = 18
    roles: List[str] = []
    bio: Optional[str] = None
```

### Características:
- ✅ Ultra-rápido (compilado)
- ✅ Validación automática de tipos
- ✅ Serialización JSON incluida
- ✅ Defaults y Optional support
- ✅ Inmutable por defecto

---

## 📝 Tipos Soportados

```python
from tachyon_api import Struct
from typing import Optional, List, Dict, Union
from datetime import datetime, date
from enum import Enum

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class Address(Struct):
    street: str
    city: str
    country: str = "Argentina"

class Product(Struct):
    # Básicos
    name: str
    price: float
    quantity: int
    in_stock: bool
    
    # Opcionales
    description: Optional[str] = None
    
    # Listas
    tags: List[str] = []
    
    # Diccionarios
    metadata: Dict[str, str] = {}
    
    # Enums
    status: Status = Status.ACTIVE
    
    # Nested structs
    warehouse: Optional[Address] = None
    
    # Datetime
    created_at: datetime = None
    
    # Union types
    discount: Union[int, float, None] = None
```

---

## ✅ Validación Automática

Tachyon valida automáticamente el body:

```python
from tachyon_api import Tachyon, Struct, Body

class CreateUser(Struct):
    name: str
    email: str
    age: int

app = Tachyon()

@app.post("/users")
def create_user(user: CreateUser = Body(...)):
    return {"created": user.name}
```

### Request válido:
```json
{"name": "John", "email": "john@example.com", "age": 25}
```
→ `200 OK`

### Request inválido:
```json
{"name": "John", "email": "john@example.com", "age": "twenty-five"}
```
→ `422 Validation Error`:
```json
{
  "success": false,
  "error": "Expected `int`, got `str`",
  "code": "VALIDATION_ERROR"
}
```

---

## 🔄 Nested Validation

```python
from tachyon_api import Struct
from typing import List

class Address(Struct):
    street: str
    city: str

class OrderItem(Struct):
    product_id: str
    quantity: int
    price: float

class Order(Struct):
    customer_name: str
    shipping_address: Address
    items: List[OrderItem]
    notes: str = ""

@app.post("/orders")
def create_order(order: Order = Body(...)):
    total = sum(item.price * item.quantity for item in order.items)
    return {
        "customer": order.customer_name,
        "city": order.shipping_address.city,
        "total": total,
        "items_count": len(order.items)
    }
```

Request:
```json
{
  "customer_name": "John Doe",
  "shipping_address": {
    "street": "123 Main St",
    "city": "Buenos Aires"
  },
  "items": [
    {"product_id": "prod_1", "quantity": 2, "price": 29.99},
    {"product_id": "prod_2", "quantity": 1, "price": 49.99}
  ]
}
```

---

## 🎭 Response Models

Valida también las respuestas:

```python
from tachyon_api import Struct

class UserResponse(Struct):
    id: str
    name: str
    email: str
    # No incluye password!

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str):
    # Aunque retornes más campos, solo se envían los del model
    return {
        "id": user_id,
        "name": "John",
        "email": "john@example.com",
        "password": "secret123"  # Este campo se filtra
    }
```

Response:
```json
{"id": "123", "name": "John", "email": "john@example.com"}
```

---

## 🛡️ Custom Validation

Para validaciones custom, hazlo en el service:

```python
from tachyon_api import Struct, HTTPException

class UserCreate(Struct):
    email: str
    password: str

@injectable
class UserService:
    def create(self, data: UserCreate):
        # Validación custom
        if "@" not in data.email:
            raise HTTPException(422, "Invalid email format")
        
        if len(data.password) < 8:
            raise HTTPException(422, "Password must be at least 8 characters")
        
        # ... crear usuario
```

---

## 📋 Comparación con Pydantic

| Feature | Tachyon (msgspec) | FastAPI (pydantic) |
|---------|------------------|-------------------|
| Performance | ⚡⚡⚡ Ultra-fast | ⚡ Fast |
| Validators | Manual en service | Decorators |
| JSON encoding | Built-in + orjson | JSON encoder |
| Memory | Muy bajo | Moderado |
| Syntax | Simple | Feature-rich |

---

## 🔗 Próximos Pasos

- [Security](./06-security.md) - Autenticación
- [Parameters](./04-parameters.md) - Tipos de parámetros
