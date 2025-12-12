# 12. CLI Tools

> Herramientas de línea de comandos para Tachyon

## 📦 Instalación

El CLI viene incluido con tachyon-api:

```bash
pip install tachyon-api
```

Verificar instalación:

```bash
tachyon --help
```

---

## 🏗️ tachyon new

Crear un nuevo proyecto:

```bash
tachyon new my-api
```

### Estructura generada:

```
my-api/
├── app.py                  # Entry point
├── config.py               # Configuración
├── requirements.txt        # Dependencias
├── modules/                # Feature modules
│   └── __init__.py
├── shared/                 # Código compartido
│   ├── __init__.py
│   ├── exceptions.py       # HTTPException helpers
│   └── dependencies.py     # Shared dependencies
└── tests/
    ├── __init__.py
    └── conftest.py         # Pytest fixtures
```

### Opciones:

```bash
# Crear en directorio específico
tachyon new my-api --path ./projects
```

---

## 🔧 tachyon generate (g)

Generar componentes de código.

### Service Completo

```bash
tachyon g service users
# o
tachyon generate service users
```

Genera:

```
modules/users/
├── __init__.py
├── users_controller.py     # Router con endpoints
├── users_service.py        # Business logic (@injectable)
├── users_repository.py     # Data access
├── users_dto.py            # Struct models
└── tests/
    └── test_users_service.py
```

### Con CRUD

```bash
tachyon g service products --crud
```

Genera endpoints CRUD:
- `GET /products` - List
- `GET /products/{id}` - Get one
- `POST /products` - Create
- `PUT /products/{id}` - Update
- `DELETE /products/{id}` - Delete

### Sin Tests

```bash
tachyon g service auth --no-tests
```

### Componentes Individuales

```bash
# Solo controller
tachyon g controller orders

# Solo repository
tachyon g repository orders
tachyon g repo orders  # alias

# Solo DTOs
tachyon g dto orders
```

### Path Custom

```bash
tachyon g service users --path src/modules
```

---

## 📄 tachyon openapi

Utilidades para OpenAPI schema.

### Exportar Schema

```bash
# A stdout
tachyon openapi export app:app

# A archivo
tachyon openapi export app:app -o openapi.json

# Con indentación
tachyon openapi export app:app -o openapi.json --indent 4
```

### Validar Schema

```bash
tachyon openapi validate openapi.json
```

Output:
```
✅ Schema is valid!
   OpenAPI version: 3.0.0
   Title: My API
   Paths: 12
```

---

## 🔍 tachyon lint

Wrapper sobre ruff para calidad de código.

### Check

```bash
# Verificar todo
tachyon lint check

# Directorio específico
tachyon lint check ./modules

# Con auto-fix
tachyon lint check --fix

# Watch mode
tachyon lint check --watch
```

### Fix

```bash
# Fix seguro
tachyon lint fix

# Fix incluyendo unsafe
tachyon lint fix --unsafe
```

### Format

```bash
# Formatear
tachyon lint format

# Solo verificar (no modifica)
tachyon lint format --check

# Ver diff
tachyon lint format --diff
```

### All (Lint + Format)

```bash
# Todo junto
tachyon lint all

# Sin auto-fix (solo reportar)
tachyon lint all --no-fix
```

---

## 📋 Resumen de Comandos

| Comando | Descripción |
|---------|-------------|
| `tachyon new <name>` | Crear proyecto |
| `tachyon g service <name>` | Generar módulo completo |
| `tachyon g controller <name>` | Generar solo controller |
| `tachyon g repository <name>` | Generar solo repository |
| `tachyon g dto <name>` | Generar solo DTOs |
| `tachyon openapi export <app>` | Exportar OpenAPI |
| `tachyon openapi validate <file>` | Validar schema |
| `tachyon lint check` | Verificar código |
| `tachyon lint fix` | Arreglar issues |
| `tachyon lint format` | Formatear código |
| `tachyon lint all` | Check + format |
| `tachyon version` | Ver versión |

---

## ⚙️ Configuración ruff

Crear `ruff.toml` o en `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
```

---

## 🔗 Próximos Pasos

- [Request Lifecycle](./13-request-lifecycle.md) - Entender el flujo
- [Best Practices](./15-best-practices.md) - Patrones recomendados
