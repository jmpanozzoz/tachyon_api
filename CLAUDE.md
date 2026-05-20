# CLAUDE.md — Tachyon API

## Regla innegociable

**Nunca incluir "Co-Authored-By: Claude" ni ninguna referencia a Claude o Anthropic en commits, PRs, changelogs ni ningún artefacto del proyecto.** Los commits son de Juan Manuel Panozzo Zenere únicamente.

---

## Qué es este proyecto

Tachyon API es un framework web Python propio, liviano, de alto rendimiento e inspirado en FastAPI. **No es un wrapper de FastAPI** — es una implementación independiente construida sobre Starlette + msgspec. El objetivo es ofrecer la misma experiencia de developer (decoradores, inyección de dependencias, OpenAPI automático) con menos overhead y dependencias.

**Stack central:** Starlette (ASGI), msgspec (validación/serialización), orjson (JSON), Typer (CLI).

---

## Arquitectura

```
tachyon_api/
├── app.py                    # Clase principal Tachyon — punto de entrada ASGI
├── router.py                 # Router para agrupar rutas con prefijo común
├── params.py                 # Marcadores: Query, Body, Path, Header, Cookie, Form, File
├── models.py                 # Struct (re-export de msgspec) + encode_json
├── di.py                     # @injectable, Depends, _registry
├── exceptions.py             # HTTPException
├── security.py               # HTTPBearer, HTTPBasic, OAuth2, APIKey*
├── cache.py                  # Decorator @cache + backends
├── background.py             # BackgroundTasks
├── files.py                  # UploadFile
├── responses.py              # TachyonJSONResponse + helpers
├── openapi.py                # OpenAPIGenerator, schemas, HTML de docs
├── testing.py                # TachyonTestClient
├── core/
│   ├── lifecycle.py          # LifecycleManager (startup/shutdown)
│   └── websocket.py          # WebSocketManager
├── processing/
│   ├── parameters.py         # ParameterProcessor — extrae todos los params del request
│   ├── dependencies.py       # DependencyResolver — resuelve @injectable y Depends()
│   └── response_processor.py # ResponseProcessor — valida y serializa respuestas
├── middlewares/
│   ├── core.py               # Infraestructura de middlewares
│   ├── cors.py               # CORS
│   └── logger.py             # Request logging
├── utils/
│   ├── type_utils.py         # TypeUtils — unwrap Optional, is_list_type, etc.
│   └── type_converter.py     # TypeConverter — conversión str → tipo para URL params
└── cli/                      # CLI tachyon (new, generate, openapi, lint)
```

### Flujo de un request

1. `Tachyon.__call__` → delega a `Starlette._router`
2. Starlette matchea la ruta → llama al `handler` closure generado en `_add_route`
3. `ParameterProcessor.process_parameters()` inspecciona la firma del endpoint e inyecta: `Request`, `BackgroundTasks`, dependencias explícitas/implícitas, `Body`, `Query`, `Header`, `Cookie`, `Form`, `File`, `Path`
4. `ResponseProcessor.call_endpoint()` llama al endpoint (sync o async)
5. `ResponseProcessor.process_response()` valida contra `response_model`, serializa con orjson, ejecuta `BackgroundTasks`

---

## Decisiones de diseño

### Por qué msgspec y no Pydantic
msgspec es entre 5-10x más rápido en serialización/deserialización. El trade-off es que los modelos son `Struct` (inmutables por defecto) en vez de clases arbitrarias. Para un framework de alta performance, este trade-off es intencional y no debe revertirse.

### Por qué Starlette como base
Starlette provee el routing ASGI, TestClient, WebSocket, y middlewares. Reimplementar eso sería reinventar la rueda innecesariamente. Tachyon agrega la capa de DX (decoradores, DI, OpenAPI, validación) sobre Starlette.

### Inyección de dependencias dual
- `@injectable` (implícita): registra la clase en `_registry`. Tachyon la instancia automáticamente si el tipo de la anotación está en el registry. Singleton por request (cacheado en `_instances_cache`).
- `Depends(callable)` (explícita): factory function, cacheada por request via `dependency_cache`.

### Por qué `_instances_cache` es por-app y no por-request
Los singletons de servicios (repositorios, servicios) se crean una vez y se reutilizan. Si necesitás scope por-request, usá `Depends(callable)` que tiene cache per-request.

---

## Convenciones de código

### General
- Python 3.10+ obligatorio. Usar `X | Y` para unions solo donde haya `from __future__ import annotations`.
- Sin comentarios obvios. Solo comentar invariantes no evidentes o workarounds específicos.
- Sin docstrings en métodos cuyo nombre ya explica qué hacen.

### Tipos
- Anotar todos los parámetros y retornos en el código del framework (no en tests).
- Usar `Optional[X]` (no `X | None`) para consistencia con el resto del codebase.
- Usar `typing.get_origin` / `typing.get_args` para introspección de genéricos — no re-implementar esa lógica.

### Manejo de errores
- Errores del cliente (input inválido) → 422 con `validation_error_response()`.
- Errores del servidor (bug interno) → 500 con `internal_server_error_response()`.
- Nunca `except Exception: pass`. Si se swallow una excepción, loggear con `logger.warning`.
- Los errores de parsing de body/form deben retornar 422, no 500.

### Tests
- Todos los tests usan `async with create_client(app) as client:` (httpx AsyncClient), **no** `TestClient` síncrono para tests nuevos.
- Cada test crea su propio `app = Tachyon()` — no mutates fixtures globales.
- Sin `assert True` ni aserciones trivialmente verdaderas.
- Testear comportamiento observable (HTTP status, response body), no estructura interna.

---

## Qué NO hacer

- **No agregar Pydantic** como dependencia ni como alternativa a msgspec.
- **No expandir el scope de `app.py`**. Ya tiene demasiadas responsabilidades. Cualquier nueva lógica compleja va en `core/`, `processing/`, o un módulo nuevo.
- **No usar `issubclass` sin verificar `isinstance(x, type)` primero** — falla con tipos genéricos como `List[Struct]`.
- **No poner lógica de negocio en el framework**. El directorio `example/` es solo para demos.
- **No usar `sys.path.insert` fuera del CLI** (donde es necesario para cargar módulos del usuario).
- **No registrar exception handlers síncronos** — bloquean el event loop. Tachyon lo advierte en log; si ves el warning en tests, corregirlo.

---

## Comandos frecuentes

```bash
# Tests
pytest tests/ -v

# Linter
ruff check tachyon_api/
ruff check tachyon_api/ --fix

# CLI (desarrollo)
python -m tachyon_api.cli.main --help
python -m tachyon_api.cli.main new mi-proyecto
python -m tachyon_api.cli.main generate service users --crud

# Correr el ejemplo
cd example && uvicorn example.app:app --reload
```

---

## Dependencias

| Paquete | Versión mínima | Por qué |
|---------|---------------|---------|
| `starlette` | `^0.47.2` | ASGI core, routing, TestClient |
| `msgspec` | `^0.19.0` | Validación + serialización ultra-rápida |
| `orjson` | `^3.11.1` | JSON encoding de alto rendimiento |
| `uvicorn` | `^0.35.0` | Servidor ASGI de desarrollo |
| `typer` | `^0.16.0` | CLI |
| `python-multipart` | `^0.0.20` | Parsing de form-data y file uploads |

Dev: `pytest`, `pytest-asyncio`, `httpx`, `ruff`.

**Nota:** `starlette >= 0.47` es requisito duro. La versión 0.19.x es incompatible con anyio 4.x.

---

## Versionado

Semantic Versioning. Breaking changes solo en major version. El framework está en `0.x` — se permiten breaking changes de API en minor versions hasta llegar a `1.0`.

Historial en `CHANGELOG.md`.
