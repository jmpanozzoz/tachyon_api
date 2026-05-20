# CLAUDE.md — Tachyon API

## Regla innegociable

**Nunca incluir "Co-Authored-By: Claude" ni ninguna referencia a Claude o Anthropic en commits, PRs, changelogs ni ningún artefacto del proyecto.** Los commits son de Juan Manuel Panozzo Zenere únicamente.

---

## Qué es este proyecto

Tachyon API es un framework web Python **opinado, minimalista y de alto rendimiento**, construido sobre Starlette + msgspec. **No es un wrapper de FastAPI** — es una implementación independiente que toma la DX de FastAPI y la ejecuta sin overhead.

El target son **aplicaciones p99**: sistemas donde la latencia en el percentil 99 importa, el throughput es una restricción real, y cada microsegundo de overhead del framework es un costo que el usuario no pidió pagar.

**Stack central (4 dependencias):** Starlette (ASGI), msgspec (validación/serialización), orjson (JSON), Typer (CLI).

---

## Filosofía central

### Menos es más — siempre

Cada dependencia, cada abstracción, cada feature tiene un costo. Si ese costo no está justificado por un caso de uso concreto y frecuente, no entra. La pregunta antes de agregar algo no es "¿podría ser útil?", es **"¿es imprescindible para el 80% de los usuarios?"**

Tachyon es **opinado por diseño**. Elegir msgspec sobre Pydantic no es una preferencia — es una decisión de arquitectura que define el target de usuario. Si alguien necesita Pydantic, FastAPI ya existe.

### Performance como feature, no como bonus

El rendimiento no es una característica opcional a agregar después. Es **un requisito de diseño desde el primer commit**. Toda decisión de implementación se evalúa contra su impacto en latencia y throughput.

Las tres preguntas ante cualquier cambio:
1. ¿Cuántos µs agrega esto a cada request?
2. ¿Se puede hacer en startup en vez de en cada request?
3. ¿Requiere una nueva allocación de objeto? ¿Puede reutilizarse?

### El overhead del framework no debería ser visible

El objetivo es que el costo de Tachyon en producción sea indistinguible del costo de uvicorn solo. Todo lo que hacemos está orientado a reducir la distancia entre "servidor ASGI puro" y "framework completo".

Estado actual: **4.25x más rápido que FastAPI**. Roadmap: **10x**.

---

## Arquitectura

```
tachyon_api/
├── app.py                    # Clase principal Tachyon — punto de entrada ASGI
├── router.py                 # Router con prefijo común
├── params.py                 # Marcadores: Query, Body, Path, Header, Cookie, Form, File
├── models.py                 # Struct (re-export de msgspec) + encode_json
├── di.py                     # @injectable, Depends, _registry
├── exceptions.py             # HTTPException
├── security.py               # HTTPBearer, HTTPBasic, OAuth2, APIKey*
├── cache.py                  # Decorator @cache + backends
├── background.py             # BackgroundTasks
├── files.py                  # UploadFile
├── responses.py              # TachyonJSONResponse/TachyonBytesResponse + helpers
├── openapi.py                # OpenAPIGenerator, generate_route(), build_param_schema()
├── testing.py                # TachyonTestClient
├── core/
│   ├── lifecycle.py          # LifecycleManager (startup/shutdown)
│   └── websocket.py          # WebSocketManager
├── processing/
│   ├── compiler.py           # compile_endpoint() — pre-compila endpoints en startup
│   ├── parameters.py         # ParameterProcessor — extrae params del request
│   ├── dependencies.py       # DependencyResolver — resuelve @injectable y Depends()
│   └── response_processor.py # ResponseProcessor — serializa y valida respuestas
├── middlewares/
│   ├── core.py
│   ├── cors.py
│   └── logger.py
├── utils/
│   ├── type_utils.py         # TypeUtils — unwrap Optional, is_list_type, etc.
│   └── type_converter.py     # TypeConverter — str → tipo para URL params
└── cli/
```

### Flujo de un request (hot path)

```
Tachyon.__call__
  → Starlette routing (F1: reemplazar con radix trie)
  → handler closure (captura CompiledEndpoint en startup)
    → ParameterProcessor.process_parameters(compiled, request)  [~0.3µs no-param]
    → ResponseProcessor.call_endpoint(compiled, kwargs)          [~0.15µs]
    → ResponseProcessor.process_response(payload, model, bg)     [~0.8µs]
      → TachyonBytesResponse (Struct) o TachyonJSONResponse (dict)
```

**Principio clave:** todo lo que puede hacerse en `_add_route()` (startup) no se hace en el request. `processing/compiler.py` es donde se pre-compila la lógica de cada endpoint.

---

## Decisiones de diseño

### Por qué msgspec y no Pydantic
msgspec valida y serializa en C. Pydantic en Python (incluso v2 tiene más overhead). El trade-off — usar `Struct` en vez de clases arbitrarias — es **intencional y permanente**. No se revierte.

### Por qué Starlette como base (y cuándo dejarla de lado)
Starlette da ASGI, TestClient, WebSocket, lifespan. Reimplementarlos sería deuda técnica enorme sin ganancia real. Sin embargo, el **routing regex lineal de Starlette es el mayor bottleneck actual** (5–8µs/req). La Fase 1 del roadmap lo reemplaza con un radix trie propio.

### Por qué endpoint pre-compilation
`inspect.signature()`, `iscoroutinefunction()`, cadena de `isinstance`, `typing.get_origin/args`, y creación de `msgspec.Decoder` corren **una sola vez en startup** y se guardan en `CompiledEndpoint`. En request time solo se consulta el descriptor. Esto eliminó ~1.5µs del ciclo anterior.

### DI dual: `@injectable` vs `Depends(callable)`
- `@injectable`: singleton app-scoped. Se crea una vez, se reutiliza. Cero overhead en request time para singletons ya cacheados.
- `Depends(callable)`: factory por request, con cache en `dependency_cache` del mismo request.
- Si no hay `KIND_DEP_CALLABLE` en el `CompiledEndpoint`, `dependency_cache` ni se crea (F2 del roadmap).

### TachyonJSONResponse hereda de JSONResponse pero bypasea __init__
`Response.__init__` de Starlette cuesta ~0.96µs (construye `MutableHeaders`). Nuestras clases de response heredan para compatibilidad `isinstance` pero setean atributos directamente. El costo bajó a ~0.27µs.

---

## Convenciones de código

### General
- Python 3.10+ obligatorio.
- Sin comentarios obvios. Solo comentar invariantes no evidentes, workarounds específicos, o decisiones de performance con impacto medible.
- Sin docstrings en métodos cuyo nombre ya explica qué hacen.
- Toda nueva función en el hot path debe tener un micro-benchmark antes y después en `benchmark/profile_breakdown.py`.

### Performance en el hot path
- **Allocaciones por request son caras.** Antes de crear un objeto por request, preguntarse si puede ser creado en startup.
- **`__slots__` en toda clase que se instancia frecuentemente** (params, descriptors, responses).
- **No usar `isinstance` donde se puede usar `type(x) is T`** — más rápido para tipos exactos.
- **Pre-compute todo en `compile_endpoint()`**, nunca en `process_parameters()`.
- **`_bare` variants** de TypeConverter evitan `unwrap_optional()` redundante cuando el tipo ya está pre-unwrapped en el descriptor.

### Tipos
- Anotar todos los parámetros y retornos en código del framework (no en tests).
- Usar `Optional[X]` para consistencia con el resto del codebase.

### Manejo de errores
- Errores del cliente → 422 con `validation_error_response()`.
- Errores del servidor → 500 con `internal_server_error_response()`.
- Nunca `except Exception: pass`. Si se swallow, loggear con `logger.warning`.

### Tests
- `async with create_client(app) as client:` — no `TestClient` síncrono.
- Cada test crea su propio `app = Tachyon()`.
- Testear comportamiento observable (HTTP status, response body), no internals.
- Sin `assert True`.

---

## Qué NO hacer — lista definitiva

**Dependencias:**
- No agregar Pydantic. Nunca. El target es msgspec.
- No agregar dependencies que no estén justificadas por un caso de uso del 80%.
- No meter en `[dependencies]` lo que pertenece a `[dev.dependencies]`.

**Performance:**
- No hacer `inspect.signature()` en request time — se hace en startup en `compile_endpoint()`.
- No crear dicts/listas innecesarios por request — minimizar allocaciones en el hot path.
- No ignorar el impacto de µs en cambios al hot path. Medir antes y después.
- No agregar middleware por default — cada middleware es overhead constante en todos los requests.

**Arquitectura:**
- No expandir `app.py`. OpenAPI va en `openapi.py`, routing irá en `routing/trie.py`, DI en `processing/dependencies.py`.
- No poner lógica de negocio en el framework. `example/` es solo demo.
- No usar `issubclass` sin `isinstance(x, type)` antes — falla con genéricos.
- No `sys.path.insert` fuera del CLI.

**API pública:**
- No hacer breaking changes en minor versions (estamos en v1.x).
- No agregar parámetros optativos que cambien semántica por default.
- No romper compatibilidad con el patrón FastAPI-like de la DX.

**Código:**
- No exception handlers síncronos — bloquean el event loop.
- No features "por si acaso" — si no hay un caso de uso concreto hoy, no entra.

---

## Comandos

```bash
# Tests
pytest tests/ -v

# Linter
ruff check tachyon_api/
ruff check tachyon_api/ --fix

# Benchmark completo vs FastAPI
bash benchmark/run_benchmark.sh

# Micro-benchmarks del hot path
python benchmark/profile_hotpath.py
python benchmark/profile_breakdown.py

# CLI
python -m tachyon_api.cli.main --help
python -m tachyon_api.cli.main new mi-proyecto
python -m tachyon_api.cli.main generate service users --crud
```

---

## Dependencias

| Paquete | Por qué está | Por qué NO se saca |
|---|---|---|
| `starlette` | ASGI, TestClient, WebSocket, lifespan | Reimplementar sería meses de deuda sin ganancia real |
| `msgspec` | Validación + serialización en C | Es la razón de ser del framework — sin Pydantic |
| `orjson` | JSON encoding C, 10x más rápido que stdlib | Sin stdlib json en el hot path |
| `uvicorn` | ASGI server | Deployment standard, no se compite con él |
| `typer` | CLI | Pequeño, rápido, suficiente |
| `python-multipart` | Form + file upload | Sin alternativa viable |

Dev: `pytest`, `pytest-asyncio`, `httpx`, `ruff`.

**Nota:** starlette >= 0.47 es requisito duro. La routing regex de Starlette se reemplaza en F1 del roadmap pero la dependencia se mantiene.

---

## Roadmap

Ver `ROADMAP.md` (gitignored — no se commitea, es documento de trabajo interno).

Resumen de fases:
- **F1** — Radix trie router (4.25x → 5.5x) — mayor win único disponible
- **F2** — Micro-optimizaciones acumuladas (5.5x → 6.5x)
- **F3** — Cython compilation del hot path (6.5x → 8x)
- **F4** — Bypass middleware Starlette (8x → 9x)
- **F5** — C extension core (9x → 10x)

---

## Versionado

Semantic Versioning. Breaking changes solo en major versions. Historial en `CHANGELOG.md`.
