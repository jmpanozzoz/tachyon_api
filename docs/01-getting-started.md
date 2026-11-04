# 01. Getting Started

> Tu primera aplicación con Tachyon en 5 minutos

## 📦 Instalación

### Con pip

```bash
pip install tachyon-api
```

### Con Poetry

```bash
poetry add tachyon-api
```

### Dependencias incluidas

Tachyon instala automáticamente:
- `starlette` - Framework ASGI base
- `uvicorn` - Servidor ASGI
- `msgspec` - Validación y serialización ultra-rápida
- `orjson` - JSON encoding/decoding rápido

### Precompiled extensions

La [versión 1.4.0 está publicada en PyPI](https://pypi.org/project/tachyon-api/1.4.0/). Incluye wheels nativos macOS ARM64 para CPython 3.10–3.13, un wheel portable y un sdist. La validación local se hizo en Mac; no acredita pruebas en Linux o Windows. En otras plataformas pip puede instalar el wheel portable, sujeto a compatibilidad de dependencias.

Los builds nativos desde fuente requieren compilador. Para construir el fallback Python desde fuente:

```bash
TACHYON_SKIP_CYTHON=1 pip install --no-binary=tachyon-api tachyon-api
```

See the [build guide](./16-cython-build.md) for platform and fallback details.

Para producción, desactivar reload:

```bash
tachyon run app:app --prod
```

El CLI detecta uvloop/httptools si están instalados y disponibles. uvloop es opcional y no está disponible en todas las plataformas.

---

## 🚀 Hello World

Crea un archivo `app.py`:

```python
from tachyon_api import Tachyon

app = Tachyon()

@app.get("/")
def hello():
    return {"message": "Hello, Tachyon!"}

@app.get("/items/{item_id}")
def get_item(item_id: int):
    return {"item_id": item_id}
```

Ejecuta el servidor:

```bash
uvicorn app:app --reload
```

Visita:
- http://localhost:8000 - Tu endpoint
- http://localhost:8000/docs - Documentación interactiva (Scalar)
- http://localhost:8000/redoc - Documentación ReDoc

---

## 🏗️ Usando el CLI

Tachyon incluye un CLI para generar proyectos:

```bash
# Crear proyecto nuevo
tachyon new my-api

# Entrar al proyecto
cd my_api

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python app.py
```

Estructura generada:

```
my_api/
├── app.py              # Entry point
├── config.py           # Configuración
├── requirements.txt    # Dependencias
├── modules/            # Módulos de la aplicación
├── shared/             # Código compartido
│   ├── exceptions.py   # Excepciones custom
│   └── dependencies.py # Dependencias compartidas
└── tests/              # Tests
    └── conftest.py     # Fixtures de pytest
```

---

## 📝 Ejemplo Completo

```python
import msgspec
from tachyon_api import Tachyon, Struct, Body, Query, HTTPException

app = Tachyon()

# Modelo de datos
class Item(Struct):
    name: str
    price: float
    description: str = ""

# Base de datos simulada
items_db = {}

@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok"}

@app.get("/items")
def list_items(skip: int = Query(0), limit: int = Query(10)):
    """Lista items con paginación."""
    all_items = list(items_db.values())
    return {"items": all_items[skip:skip+limit], "total": len(all_items)}

@app.get("/items/{item_id}")
def get_item(item_id: str):
    """Obtiene un item por ID."""
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return items_db[item_id]

@app.post("/items")
def create_item(item: Item = Body()):
    """Crea un nuevo item."""
    import uuid
    item_id = str(uuid.uuid4())
    items_db[item_id] = {"id": item_id, **msgspec.structs.asdict(item)}
    return items_db[item_id]

@app.delete("/items/{item_id}")
def delete_item(item_id: str):
    """Elimina un item."""
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    del items_db[item_id]
    return {"deleted": True}
```

---

## 🔗 Próximos Pasos

1. [Arquitectura](./02-architecture.md) - Estructura de proyecto recomendada
2. [Dependency Injection](./03-dependency-injection.md) - Inyección de dependencias
3. [Parameters](./04-parameters.md) - Tipos de parámetros disponibles
