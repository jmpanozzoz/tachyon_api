# CLAUDE.md — Tachyon API

## Reglas innegociables

**1. Sin Co-Author.** Nunca incluir "Co-Authored-By: Claude" ni ninguna referencia a Claude o Anthropic en commits, PRs, changelogs ni ningún artefacto del proyecto. Los commits son de Juan Manuel Panozzo Zenere únicamente.

**2. Changelog siempre actualizado.** Ante cualquier commit que implique un cambio de versión (major, minor o patch), actualizar `CHANGELOG.md` antes de hacer el commit. Sin excepción. El formato sigue Keep a Changelog. Cada entrada debe tener: versión, fecha, y categorías (Added / Changed / Fixed / Security / Performance / Removed).

**3. Branching strategy.** Todo trabajo nuevo se hace en una rama propia por feature:
- `feature/<nombre>` para features nuevas (ej: `feature/radix-router`)
- `feature/v1.3.X-<slug>` para fases del plan 1.3.x → 1.4.0 (ej: `feature/v1.3.1-zero-alloc`)
- `fix/<nombre>` para bug fixes
- `perf/<nombre>` para optimizaciones de performance
- El flujo es siempre: `feature/*` → merge a `dev` → cuando sale release, `dev` → merge a `main`
- Nunca commitear directamente a `dev` ni a `main` trabajo de feature en progreso.

**4. Parity `.py` ↔ `.pyx`.** Toda modificación a un módulo del hot path con versión Cython debe aplicarse simultáneamente en ambos archivos. `scripts/check_py_pyx_parity.py` corre en CI y bloquea merges con drift de API. Logic drift se cubre con la suite — que se ejecuta **en ambos modos**: pure-Python (`TACHYON_SKIP_CYTHON=1`) y Cython compilado. Ambas tienen que estar verdes antes de mergear a `dev`.

**5. Extras opcionales nunca son runtime.** `[fast]` (cython), `[dev-tui]` (textual), `[migrate]` (libcst), `[benchmark]` (fastapi+pydantic) son extras de Poetry. Nada de eso puede importarse desde `tachyon_api/` en módulos del runtime — solo desde `tachyon_api/cli/` o `benchmark/`. Si el extra falta, el comando que lo necesita debe mostrar mensaje claro con la instrucción de install, no stacktrace.

---

## Qué es este proyecto

Tachyon API es un framework web Python **opinado, minimalista y de alto rendimiento**, construido sobre Starlette + msgspec. **No es un wrapper de FastAPI** — es una implementación independiente que toma la DX de FastAPI y la ejecuta sin overhead.

El target son **aplicaciones p99**: sistemas donde la latencia en el percentil 99 importa, el throughput es una restricción real, y cada microsegundo de overhead del framework es un costo que el usuario no pidió pagar.

**Stack central (6 dependencias runtime):** Starlette (ASGI), msgspec (validación/serialización), orjson (JSON), uvicorn (server), Typer (CLI), python-multipart (form/file).

**Estado actual:** v1.3.0 publicada en PyPI con 27 wheels Cython precompiladas — **5.61× FastAPI**, 370+ tests verdes en pure-Python y compilado.

**Target 1.4.0:** ~12× FastAPI (ceiling Python/Cython) + CLI revamp + `tachyon migrate` + AI skills dinámicas. Plan completo en `ROADMAP.md` (sección "v1.3.x → v1.4.0 — Plan maestro").

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

---

## Arquitectura

```
tachyon_api/
├── __init__.py                  # API pública (Tachyon, Struct, Body, Query, ...)
├── app/                         # Fachada + colaboradores del app object
│   ├── __init__.py              # class Tachyon — compone todo, ASGI entry
│   ├── _404.py / _405.py        # bodies + start dicts para errores
│   ├── _asgi_entry.py           # dispatch HTTP/WebSocket/lifespan
│   ├── _asgi_handler.py         # fast-path para endpoints sin params
│   ├── _docs_routes.py          # /docs, /redoc, /openapi.json
│   ├── _docs_schemas.py         # CommonSchemas registrados al boot
│   ├── _exception_table.{py,pyx}# tabla de exception handlers
│   ├── _fast_asgi_factory.py    # construye closures por endpoint
│   ├── _handler_factory.py      # idem, con params
│   ├── _http_dispatch.py        # router HTTP → trie | non-HTTP → Starlette
│   ├── _mw_stack.py             # tracking de middlewares
│   ├── _registry.py             # lista de rutas registradas
│   └── _route_installer.py      # add_route() unificado
├── router.py                    # Router con prefijo común
├── params.py                    # Marcadores: Query, Body, Path, Header, Cookie, Form, File
├── models.py                    # Struct (re-export de msgspec) + encode_json
├── di.py                        # @injectable, Depends, _registry
├── exceptions.py                # HTTPException
├── security/                    # HTTPBearer, HTTPBasic, OAuth2, APIKey*
├── responses/                   # TachyonJSONResponse/TachyonBytesResponse + helpers
├── cache.py                     # Decorator @cache + backends
├── background.py                # BackgroundTasks
├── files.py                     # UploadFile
├── openapi/                     # OpenAPIGenerator, schema builders
├── testing.py                   # TachyonTestClient
├── server.py                    # TachyonHTTPProtocol (opt-in)
├── _server_fast.pyx             # protocolo HTTP custom (experimental)
├── core/
│   ├── lifecycle.py             # LifecycleManager (startup/shutdown)
│   └── websocket.py             # WebSocketManager
├── processing/
│   ├── compiler.{py,pyx}        # compile_endpoint() — pre-compila endpoints en startup
│   ├── parameters.{py,pyx}      # ParameterProcessor — extrae params del request
│   ├── response_processor.{py,pyx} # serializa y valida respuestas
│   ├── dispatch.{py,pyx}        # TachyonDispatcher — dispatch trie → handler
│   ├── scope.{py,pyx}           # TachyonScope — wrapper liviano sobre scope ASGI
│   ├── _extractors/             # un extractor por tipo (path/query/body/header/cookie/form/file/...)
│   │   └── *.{py,pyx,pxd}       # 10 extractores en triple variante
│   └── dependencies/
│       └── _*.{py,pyx}          # resolver, scope_cache, class/callable factories, circular detector, sig_cache
├── routing/
│   └── trie.{py,pyx}            # RadixTrie — O(k) lookup, fallback Python
├── middlewares/
│   ├── core.py / cors.py / logger.py
├── utils/
│   ├── type_utils.py            # unwrap Optional, is_list_type, etc.
│   └── type_converter.py        # str → tipo para URL params
└── cli/
    ├── main.py                  # entrypoint typer
    ├── commands/                # new, run, routes, generate, openapi, lint, skill
    └── templates/               # ProjectTemplates, ServiceTemplates, ai_skill
```

### Patrón `.py` / `.pyx` (Cython opcional)

Cada módulo del hot path tiene versión pure Python y versión Cython:
- `.py` — siempre presente, es el fallback automático
- `.pyx` — compilado a `.so` con `python setup.py build_ext --inplace` (o vía wheels precompiladas de PyPI)
- `.pxd` — declaraciones C cuando otro `.pyx` necesita `cimport`
- Python prefiere `.so` sobre `.py` automáticamente al importar
- Sin cambios de código necesarios — el framework funciona igual en ambos casos

**Módulos con versión Cython (27 extensiones):**

| Área | Módulos |
|---|---|
| Routing | `routing/trie` |
| Processing core | `processing/compiler`, `processing/parameters`, `processing/response_processor`, `processing/dispatch`, `processing/scope` |
| Extractors | `processing/_extractors/{body, body_limit, cookie, file, form, header, path, query, query_list, _missing}` |
| Dependencies | `processing/dependencies/{_resolver, _scope_cache, _class_factory, _override_lookup, _circular_detector}` |
| App glue | `app/_exception_table` |
| Server (experimental) | `_server_fast` |

### Flujo de un request (hot path)

```
Tachyon.__call__ → ASGIEntry
  → HTTPDispatcher (HTTP) | Starlette router (WebSocket/lifespan)
  → TachyonDispatcher.dispatch (Cython): RadixTrie.match() — O(k)
  → _ASGIHandler (sin params) OR handler closure (con params)
    → ParameterProcessor.process_parameters(compiled, request)  [~0.3µs no-param]
    → ResponseProcessor.call_endpoint(compiled, kwargs)          [~0.15µs]
    → ResponseProcessor.process_response(payload, model, bg)     [~0.8µs]
      → TachyonBytesResponse (Struct) | TachyonJSONResponse (dict)
```

**Notas de compatibilidad:**
- `scope["app"] = self` — `self` es `Tachyon`, no `Starlette`. Middleware que hace `isinstance(scope["app"], Starlette)` retornará False.
- Starlette's `ServerErrorMiddleware` y `ExceptionMiddleware` se bypasean para HTTP. Excepciones se manejan por try/except en cada handler closure + `ExceptionTable`.
- `routing/trie` trata trailing slashes como equivalentes: `/users` y `/users/` matchean el mismo handler.

**Principio clave:** todo lo que puede hacerse en `RouteInstaller.install()` (startup) no se hace en el request. `processing/compiler` es donde se pre-compila la lógica de cada endpoint.

---

## Decisiones de diseño

### Por qué msgspec y no Pydantic
msgspec valida y serializa en C. Pydantic en Python (incluso v2 tiene más overhead). El trade-off — usar `Struct` en vez de clases arbitrarias — es **intencional y permanente**. No se revierte.

### Por qué Starlette como base
Starlette da TestClient, WebSocket y lifespan listos. Reimplementarlos sería deuda técnica enorme sin ganancia real. El routing regex de Starlette ya **no** está en el hot path: lo reemplazamos con `RadixTrie` desde v1.1.0; Starlette solo dispatcha WebSocket y lifespan.

### Por qué endpoint pre-compilation
`inspect.signature()`, `iscoroutinefunction()`, cadena de `isinstance`, `typing.get_origin/args`, y creación de `msgspec.Decoder` corren **una sola vez en startup** y se guardan en `CompiledEndpoint`. En request time solo se consulta el descriptor.

### DI dual: `@injectable` vs `Depends(callable)`
- `@injectable`: singleton app-scoped por default. Soporta scopes (`SCOPE_REQUEST`, etc.).
- `Depends(callable)`: factory por request, con cache en `dependency_cache` del mismo request.
- Si el endpoint no tiene `KIND_DEP_CALLABLE` **ni** clases con scope ≠ singleton, `dependency_cache` no se crea. Esta es la check que arregló v1.2.993 (parity entre `compiler.py:98` y `compiler.pyx:115`).

### Response classes bypaseando `__init__` de Starlette
`Response.__init__` de Starlette cuesta ~0.96µs (construye `MutableHeaders`). `TachyonJSONResponse`/`TachyonBytesResponse` heredan para compatibilidad `isinstance` pero setean atributos directamente. El costo bajó a ~0.27µs.

---

## Convenciones de código

### Hot path — reglas load-bearing

Estas son las que **rompen performance si no se respetan**. Aplican a `routing/`, `processing/`, `app/_*.py` y cualquier código que corra por request.

- **Allocaciones por request son caras.** Antes de crear un objeto por request, preguntarse si puede ser creado en startup.
- **`__slots__` en toda clase que se instancia frecuentemente** (params, descriptors, responses, dispatcher state).
- **`type(x) is T` en vez de `isinstance(x, T)`** cuando alcanza con el tipo exacto — es una instrucción de máquina vs lookup de MRO.
- **Pre-compute todo en `compile_endpoint()`**, nunca en `process_parameters()`.
- **`_bare` variants** de TypeConverter evitan `unwrap_optional()` redundante cuando el tipo ya está pre-unwrapped en el descriptor.
- **No `inspect.signature()` en request time** — se hace en startup en `compile_endpoint()`.
- **No dicts/listas innecesarios por request.**
- **Toda nueva función en el hot path** debe tener micro-benchmark antes/después en `benchmark/profile_breakdown.py`. Si no podés mostrar el delta, no entra.

### Estilo general

- Python 3.10+ obligatorio.
- Sin comentarios obvios. Solo comentar invariantes no evidentes, workarounds específicos, o decisiones de performance con impacto medible.
- Sin docstrings en métodos cuyo nombre ya explica qué hacen.

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
- La suite tiene que pasar en **ambos modos** (compilado y `TACHYON_SKIP_CYTHON=1`). CI lo verifica.

### AI / Skills

- El contenido de skills (`install-skill`) **se genera por introspección** del paquete, no se hardcodea en templates. Source of truth: `__all__` de `tachyon_api/__init__.py`, comandos registrados en `cli/main.py`, templates de `ServiceTemplates`.
- Si agregás una clase pública al `__all__`, debe aparecer en el skill al regenerar sin tocar el template.
- Excepción permitida: snippets conceptuales (filosofía, diferencias con FastAPI) que no derivan de código — esos sí van hardcoded en `cli/templates/ai_skill.py`.

---

## Mapa por bloque de trabajo (1.3.x → 1.4.0)

Para cualquier rama del plan, este es el entry point + qué no romper. Detalle completo en `ROADMAP.md`.

### Bloque A — Performance ceiling (v1.3.1 → v1.3.6)

- **Entry points:** `routing/trie.pyx`, `processing/compiler.{py,pyx}`, `processing/parameters.{py,pyx}`, `processing/dispatch.{py,pyx}`.
- **No romper:** API pública de `CompiledEndpoint` y `ParamDescriptor`, comportamiento de DI scopes, semántica de trailing slash.
- **Validar con:** `benchmark/profile_breakdown.py` (delta µs por fase), `bash benchmark/run_benchmark.sh` (× vs FastAPI), `scripts/check_py_pyx_parity.py`.
- **Pre-trabajo:** resolver HF-01 (`_EMPTY_PARAMS` singleton en `trie.py`) antes de F6.

### Bloque B — CLI revamp (v1.3.7 → v1.3.9)

- **Entry points:** `cli/commands/*.py`, `cli/main.py`. Nuevos: `cli/commands/doctor.py`, `cli/commands/dev.py`.
- **No romper:** signatures actuales de `tachyon new`, `tachyon run`, `tachyon generate`, `tachyon routes`. Funcionar en TTY sin color.
- **Dependencias nuevas:** `rich` ya transitiva de typer (sin agregar). `textual` solo en extra `[dev-tui]`. Importar bajo `try/except ImportError` con mensaje claro.

### Bloque C — Migrate FastAPI/Starlette (v1.3.10 → v1.3.11)

- **Entry points:** `cli/commands/migrate.py` (nuevo). Lógica de AST en `cli/migrate/` (nuevo módulo).
- **Auto-detección de proyecto:** sin argumentos, escanea cwd buscando imports `fastapi`/`starlette`, `pyproject.toml` con esas deps, o `app.py`/`main.py`/`application.py` con `FastAPI(...)`/`Starlette(...)`. Si no detecta, pide path explícito — no asume.
- **Reglas innegociables del bloque:**
  - `scan` es **read-only**, cero side effects.
  - `apply` requiere backup automático (`.tachyon-migrate-backup/<timestamp>/`) salvo `--no-backup` explícito.
  - `apply` corre tests del proyecto target antes y después; si la suite estaba verde y queda roja → **rollback automático**.
  - Patrones no portables (Pydantic validators, `dependency_overrides` con scopes custom, etc.) se marcan como TODO, **nunca** se tocan.
- **Dependencias nuevas:** `libcst` en extra `[migrate]`.

### Bloque D — AI integration (v1.3.12 → v1.3.13)

- **Entry points:** `cli/commands/skill.py` (rediseño), `cli/commands/ai.py` (nuevo con `explain` y `context`).
- **No romper:** los archivos que `install-skill` ya genera (`.cursorrules`, `CLAUDE.md` snippet, `copilot-instructions.md`, `opencode/rules.md`, `AGENTS.md`) siguen existiendo igual; se **agregan** formatos nuevos (`.claude/skills/tachyon/SKILL.md`, `.cursor/skills/tachyon.md`).
- **Source of truth:** introspección del paquete instalado. Ver regla "AI / Skills" arriba.

### Bloque E — Cierre (v1.3.14 → v1.3.15 → v1.4.0)

- HF-01, HF-04, refactor `tests/test_coverage_gaps.py` por tema, mover `fastapi`/`pydantic` a extra `[benchmark]`, audit imports.
- RC interno `v1.4.0rc1` en `dev`, una semana de uso, tag final en `main`.

---

## Qué NO hacer — lista definitiva

**Dependencias:**
- No agregar Pydantic. Nunca. El target es msgspec.
- No agregar dependencies que no estén justificadas por un caso de uso del 80%.
- No meter en `[tool.poetry.dependencies]` lo que pertenece a `[tool.poetry.group.dev.dependencies]` o a un extra opcional.
- No importar desde extras opcionales (`textual`, `libcst`, `cython`) en código del runtime (`tachyon_api/` fuera de `cli/`).

**Performance:**
- No hacer `inspect.signature()` en request time — se hace en startup en `compile_endpoint()`.
- No crear dicts/listas innecesarios por request — minimizar allocaciones en el hot path.
- No ignorar el impacto de µs en cambios al hot path. Medir antes y después.
- No agregar middleware por default — cada middleware es overhead constante en todos los requests.

**Arquitectura:**
- No expandir `app/__init__.py` (fachada). Los colaboradores van como módulos `app/_*.py` separados.
- No poner lógica de negocio en el framework. `example/` es solo demo.
- No usar `issubclass` sin `isinstance(x, type)` antes — falla con genéricos.
- No `sys.path.insert` fuera del CLI.

**Cython:**
- No modificar un `.pyx` sin replicar el cambio en su `.py` sibling (y viceversa). El parity script bloquea API drift; logic drift solo lo cubren los tests.
- No agregar Cython compilation a un módulo nuevo sin micro-benchmark que justifique el delta. Cython tiene costo de mantenimiento (parity, debugging, build).

**API pública:**
- No hacer breaking changes en minor versions (estamos en v1.x).
- No agregar parámetros optativos que cambien semántica por default.
- No romper compatibilidad con el patrón FastAPI-like de la DX.

**Código:**
- No exception handlers síncronos — bloquean el event loop.
- No features "por si acaso" — si no hay un caso de uso concreto hoy, no entra.
- No hardcodear contenido de skills que se puede derivar por introspección.

---

## Comandos

### Tests
```bash
pytest tests/ -v                              # suite completa (modo activo)
TACHYON_SKIP_CYTHON=1 pytest tests/ -v        # forzar modo pure-Python
python scripts/check_py_pyx_parity.py         # parity API .py ↔ .pyx
```

### Lint
```bash
ruff check tachyon_api/
ruff check tachyon_api/ --fix
```

### Benchmark
```bash
bash benchmark/run_benchmark.sh               # benchmark completo vs FastAPI
python benchmark/profile_hotpath.py           # micro-benchmark hot path
python benchmark/profile_breakdown.py         # breakdown µs por componente
```

### Build Cython
```bash
python setup.py build_ext --inplace           # compila los 27 .pyx a .so localmente
TACHYON_SKIP_CYTHON=1 python setup.py build   # build pure-Python (CI fallback)
```

### CLI del framework
```bash
tachyon new mi-proyecto
tachyon run                                    # uvloop + httptools + reload
tachyon generate service users --crud
tachyon routes
tachyon install-skill                          # AI context para Cursor/Claude/Copilot/...
python -m tachyon_api.cli.main --help
```

---

## Dependencias

### Runtime (Poetry `[tool.poetry.dependencies]`)

| Paquete | Por qué está | Por qué NO se saca |
|---|---|---|
| `starlette` | TestClient, WebSocket, lifespan | Reimplementar sería meses de deuda sin ganancia real |
| `msgspec` | Validación + serialización en C | Es la razón de ser del framework — sin Pydantic |
| `orjson` | JSON encoding C, 10x más rápido que stdlib | Sin stdlib json en el hot path |
| `uvicorn` | ASGI server | Deployment standard, no se compite con él |
| `httptools` | HTTP parser C-backed para uvicorn | Crítico para los números del benchmark |
| `typer` | CLI | Pequeño, rápido, suficiente |
| `python-multipart` | Form + file upload | Sin alternativa viable |

### Dev (`[tool.poetry.group.dev.dependencies]`)

`pytest`, `pytest-asyncio`, `httpx`, `ruff`, `cython`.

### Extras opcionales

| Extra | Paquetes | Para qué |
|---|---|---|
| `[fast]` | `cython` | Build from sdist en plataformas sin wheel precompilada |
| `[dev-tui]` | `textual` *(planned 1.3.9)* | `tachyon dev` con TUI live |
| `[migrate]` | `libcst` *(planned 1.3.11)* | `tachyon migrate apply` (AST rewrites) |
| `[benchmark]` | `fastapi`, `pydantic` *(planned 1.3.14)* | Solo para correr `benchmark/run_benchmark.sh` |

**Regla:** ninguno de estos paquetes puede importarse desde código del runtime. Solo desde `cli/` o `benchmark/`, y bajo `try/except ImportError` con mensaje de install si falta.

---

## Roadmap

Ver `ROADMAP.md` (gitignored — no se commitea, es documento de trabajo interno).

**Resumen v1.3.x → v1.4.0:**
- **Bloque A** (1.3.1–1.3.6): F6–F11 performance, ~5.61× → ~12× FastAPI.
- **Bloque B** (1.3.7–1.3.9): CLI Rich, `doctor`, `dev` (TUI).
- **Bloque C** (1.3.10–1.3.11): `tachyon migrate scan` + `apply` con auto-detección de proyecto FastAPI/Starlette.
- **Bloque D** (1.3.12–1.3.13): skills dinámicas + `tachyon ai explain/context`.
- **Bloque E** (1.3.14–1.3.15 → 1.4.0): cleanup, RC, release.

**Más allá de 1.4.0 (v2.x):** server binding en C, Rust core con PyO3, ABI no-ASGI. Out of scope hasta cerrar 1.4.0.

---

## Versionado

Semantic Versioning. Breaking changes solo en major versions. Historial en `CHANGELOG.md`.
