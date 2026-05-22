# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — v1.2.0

### Security

- **`files.py`** — `UploadFile` now subclasses Starlette's version and sanitizes `filename` at construction time: strips null bytes and directory components to prevent path traversal attacks.
- **`responses.py`** — `response_validation_error_response` no longer echoes internal error details in the HTTP response body; details are logged at WARNING level only.
- **`middlewares/cors.py`** — `CORSMiddleware` defaults changed to `allow_origins=()` and `allow_headers=()`; `allow_methods` defaults to explicit safe verbs instead of `"*"`. CORS is now opt-in — callers must list origins explicitly.
- **`security.py`** — `APIKeyQuery` docstring warns that query-parameter tokens appear in server logs, browser history, and Referer headers.
- **`middlewares/security_headers.py`** — New `SecurityHeadersMiddleware`: opt-in middleware that injects `x-content-type-options`, `x-frame-options`, `referrer-policy`, and `x-permitted-cross-domain-policies` on every HTTP response. HSTS and CSP available via constructor params.
- **`processing/parameters.py`** — Path parameters containing null bytes (`\x00`) are rejected with 422 before type conversion.

### Fixed

- **`background.py`** — `BackgroundTasks.run_tasks()` no longer swallows task exceptions silently; failures are logged at WARNING with full traceback (`exc_info=True`).
- **`core/lifecycle.py`** — Startup handlers now raise `RuntimeError` on failure (with the original exception as cause), preventing the app from booting in a broken state. Shutdown handlers log failures at WARNING and continue processing remaining handlers.
- **`cache.py`** — `RedisCacheBackend.clear()` now calls `flushdb()` (current DB only) instead of silently no-oping. Falls back to `flushall()` if `flushdb()` is unavailable.

### Performance

- **`processing/response_processor.py`** — `msgspec.convert()` is skipped when `type(payload) is response_model`, avoiding a C-level conversion call for endpoints that already return the correct type.

### Performance

**F12b (Cython) — default-headers cache + compiled direct write** (`feature/server-binding-cython`)

- New `tachyon_api/_server_fast.pyx`: Cython-compiled `tachyon_direct_write` with a
  module-level `default_headers` bytes cache. The Date header changes ≤ once per second;
  at 50k+ req/s the cache eliminates the per-request `for name,value in default_headers`
  loop + `b"".join()` — replaced by a single bytes comparison and a pointer return.
- `server.py`: tries `from ._server_fast import tachyon_direct_write` at import time;
  falls back to the pure-Python implementation when `[fast]` extensions are not compiled.
- `setup.py` + `pyproject.toml`: `_server_fast.pyx` added to Cython build.
- **Measured gains (Hello World, uvicorn + uvloop)**:
  - 1 connection: **+5.7%**
  - 4 connections: **+8.5%**
  - 10 connections: **+6.3%**
  - 50 connections: **+5.4%**
  - 100 connections: +1.6% (asyncio amortises awaits at high concurrency)
- At the standard wrk benchmark (c=100) the gain is within noise; at realistic production
  concurrency (c=4–50) it is consistently +5–8%.

**F12 — Server binding: direct transport write** (`feature/server-binding`)

- New `tachyon_api/server.py`: `TachyonHTTPProtocol` — drop-in uvicorn HTTP/1.1 protocol
  subclass that injects `_tachyon_cycle` into the ASGI scope. `TachyonDispatcher` and
  `_fast_asgi` detect the key and call `tachyon_direct_write()` instead of 2× `await send()`.
- `tachyon_direct_write(cycle, response)`: module-level function that builds the full
  HTTP/1.1 response bytes (status + default_headers + content-length + content-type + body)
  and issues two synchronous `transport.write()` calls, then updates the uvicorn cycle state
  (response_started, response_complete, keep_alive, on_response callback).
- `tachyon_api.server.run(app, **kwargs)`: convenience launcher that passes
  `http=TachyonHTTPProtocol` to `uvicorn.run()`.
- **F12a** (always active): `response.__call__` coroutine eliminated — sends issued inline
  in `TachyonDispatcher.__call__` and `_fast_asgi`, saving one Python coroutine frame.
- **F12b** (TachyonServer required): infrastructure in place. In pure Python, `b"".join()`
  overhead and Python function call cost neutralize the 2× await savings (asyncio amortizes
  awaits across concurrent connections). True F12b gains require Cython compilation of
  `tachyon_direct_write` to eliminate Python object overhead — filed as a v2.x task.
- `responses.py`: `_HTTP_STATUS_LINES` cache, `_HTTP_CL_PREFIX`, `_HTTP_CT_JSON_CRLF2`
  constants for use in `tachyon_direct_write`.

**F11 — C stdlib fast path: memchr + strtol/strtod** (`feature/nogil-sections`)

- `routing/trie.pyx`: `PyUnicode_AsUTF8AndSize` called once per `match()` — returns
  a C pointer to the path bytes in O(1) for ASCII (CPython caches UTF-8 repr in compact
  Unicode objects). `memchr` replaces `path.find("/", pos)` Python method call in the
  inner segment loop — C-level byte scan (~3ns) vs Python method call (~71ns),
  saving **~68ns per path segment**.
- `processing/parameters.pyx`: `strtol`/`strtod` module-level `cdef` helpers
  (`_fast_int`, `_fast_float`) replace `TypeConverter.convert_value_bare()` for `int`
  and `float` params. Uses `PyUnicode_AsUTF8AndSize` + C stdlib functions directly —
  no Python function call boundary, no exception handling overhead.
  Saving: **~40ns per int param**, **~85ns per float param**.
- `_process_query` and `_process_path` in `parameters.pyx` updated to call
  `_fast_int`/`_fast_float` before falling through to `TypeConverter` for other types.
- Pure Python `.py` files unchanged — these optimizations are Cython-only (pure Python
  `int()` is already optimal at ~69ns and ctypes overhead exceeds the gain).
- Measured gains per request (Cython compiled, typical parameterised endpoint):
  - 2 path segments: **~136ns saved** from memchr
  - 1 int path param: **~40ns saved** from strtol
  - Total per request with path + int param: **~176ns**

**F10 — Pre-built header tuples — pooled response headers** (`feature/pooled-responses`)

- `responses.py`: added `_CT_TUPLE = (_CT_NAME, _CT_JSON)` — singleton content-type
  header tuple; previously re-created on every response (~20ns per response).
- `responses.py`: added `_CL_TUPLE_CACHE: dict` — 65536 pre-built `(b"content-length", b"N")`
  tuples for body sizes 0–65535 bytes (~4MB startup cost). Inline dict lookup
  `_CL_TUPLE_CACHE[n] if n < 65536 else ...` avoids one tuple allocation and one
  `_cl_bytes()` call per response.
- `TachyonJSONResponse.__init__`, `TachyonBytesResponse.__init__`,
  `_InternalErrorResponse` headers: updated to use inline lookup.
- The headers *list* is still created fresh per response — shared lists are unsafe
  because CORS and other middlewares may mutate `message["headers"]` in place.
- Micro-benchmark delta: headers list creation **138ns → 59ns (−79ns, −57%)**.

**F9 — `_trie_dispatch` to Cython cdef class** (`feature/cython-dispatch`)

- New `processing/dispatch.py` + `processing/dispatch.pyx`: `TachyonDispatcher` —
  `cdef class` that replaces the pure-Python `_trie_dispatch` method as the innermost
  ASGI callable in `_build_http_app`.
- Cython gains: `cdef int status` (no Python int boxing), `cdef object handler/path_params`
  (direct C pointer locals, no Python name-lookup overhead), C-level struct field reads
  for all `self.*` constants (`_trie`, `_404_start`, etc.).
- `type(handler) is self._asgi_handler_class` — C type-pointer comparison in Cython,
  faster than `isinstance` for exact-type checks.
- `app.py`: `__init__` instantiates `self._dispatcher = TachyonDispatcher(...)` once at
  startup. `_build_http_app` and `_make_http_dispatch` both use `self._dispatcher`
  instead of the Python `_trie_dispatch` bound method.
- `setup.py`: `dispatch.pyx` added to Cython extension build.
- Savings: neutral in pure Python; Cython path: ~80ns saved from removing Python int
  boxing + C-level struct reads on every HTTP request.

**F8 — Eliminate Request object from hot path** (`feature/no-request`)

- New `processing/scope.py` + `processing/scope.pyx`: `TachyonScope` — thin ASGI scope
  wrapper with `__slots__`, direct C-field None checks (Cython `cdef class`), and no
  Starlette class hierarchy. Implements the exact subset of the Request API that
  `process_parameters` uses: `path_params`, `query_params`, `headers`, `cookies`,
  `body()`, `form()`.
- `app.py`: `_trie_dispatch` creates `TachyonScope(scope, receive, send)` instead of
  `Request(scope, receive, send)` for parameterised endpoints.
- `KIND_REQUEST` params: `as_request()` materialises the full Starlette `Request`
  lazily — only when the endpoint explicitly declares `request: Request`.
- Exception handlers: `request.as_request()` called on error paths only — no overhead
  on the happy path.
- `processing/dependencies.py`: `resolve_callable_dependency` calls `as_request()` when
  injecting `Request` into callable dependencies.
- `setup.py`: `scope.pyx` added to the Cython extension build.
- Micro-benchmark delta: `TachyonScope()` **221ns** vs `Request()` **398ns** → **−176ns/req**
  on all parameterised endpoints. Exceeds the F8 roadmap target of −100ns.

**F7 — Direct dispatch — list args, no kwargs dict** (`feature/direct-dispatch`)

- `processing/parameters.py` + `parameters.pyx`: `process_parameters` now returns a
  `list` (pre-allocated `[None] * compiled.param_count`) instead of a `dict`.
  Each param writes `args[i] = value` — C array index write in Cython vs
  `PyDict_SetItem` with string hashing.
- `processing/response_processor.py` + `response_processor.pyx`: `call_endpoint`
  accepts `list args` and calls `func(*args)` instead of `func(**kwargs)`.
  Positional call eliminates the per-arg key lookup Python does during `**dict` unpacking.
- All `_process_*` helper methods refactored to return `(value, error)` tuples instead
  of writing to the dict — cleaner separation and enables further Cython optimization.
- `processing/compiler.py`: `CompiledEndpoint` gains `param_count` field
  (pre-computed `len(params)`) — avoids `len()` call per request in the processor.
- `app.py`: fast-paths updated to pass `[]` instead of `{}` to `call_endpoint`.
- Micro-benchmark delta (pure Python): `func(**kwargs)` **140ns → 68ns (-51%)** for
  the call itself; net saving per request ~72ns on the call overhead.
  Larger gains expected in Cython path where list index writes become `PyList_SET_ITEM`.

**F6 — Zero-allocation routing** (`feature/zero-alloc-routing`)

- `routing/trie.py` + `routing/trie.pyx`: `match()` now inlines segment traversal
  directly — no `_segments()` list allocation, no generator. The path string is
  scanned with `str.find('/')` in a tight loop, extracting slices in place.
- `path_params` dict is lazily allocated: starts as `None`, upgraded to `{}` only
  when the first param segment is actually encountered. Static routes (`/health`,
  `/docs`, etc.) produce zero dict allocations during matching.
- `_EMPTY_PARAMS = MappingProxyType({})` — module-level immutable sentinel returned
  for routes with no path parameters and for not-found / method-not-allowed responses.
  One allocation at module load; replaces a fresh `{}` per request.
- `processing/compiler.py`: `CompiledEndpoint` gains `has_path_params` flag
  (pre-computed at registration) — available for F7/F8 to skip path-param extraction
  without re-iterating `params`.
- Micro-benchmark delta (pure Python): static route match **~0.21µs**;
  1-param route **~0.23µs**; 2-param route **~0.27µs**.

---

## [1.1.0] - 2026-05-20

### ⚠️ Breaking Changes (internal APIs only)

- **`KIND_*` constants**: Changed from `str` to `int` in `processing/compiler.py`.
  Public API unaffected. If you imported these constants directly and compared them
  as strings (`kind == "query"`), update to integer comparison (`kind == KIND_QUERY`).
- **`RadixTrie.match()` return type**: The 4th return value for `_METHOD_NOT_ALLOWED`
  changed from `Set[str]` to `str` (pre-sorted Allow header value like `"GET, POST"`).
  Internal API — no user-facing impact.
- **`scope["app"]`**: Now set to `Tachyon` instance (not `Starlette`). Third-party
  middleware doing `isinstance(scope["app"], Starlette)` will return False.
- **HTTP routing**: `_add_route` no longer appends Starlette `Route` objects to
  `self._router.routes`. Code accessing `app._router.routes` directly will see an
  empty list. Use `app.routes` (public API) instead.
- **Trailing slashes**: The radix trie ignores trailing slashes — `/users` and `/users/`
  resolve to the same handler. Previously Starlette would 307 redirect; now both match.

### Performance

**Phase 1 — Radix trie router** (`feature/radix-router`)
- Replaced Starlette's O(N × regex) route scanning with an O(k) radix trie router
  where k = number of path segments (typically 2–5).
- `tachyon_api/routing/trie.py`: `RadixTrie` with static dict children (O(1) lookup)
  and a single param branch per node. Handles FOUND / NOT_FOUND / METHOD_NOT_ALLOWED.
- `app.py`: replaces `self._router.router.middleware_stack` (Starlette's lazy-built
  dispatch loop) with a custom HTTP dispatcher before the first request. HTTP goes
  through the trie; WebSocket and lifespan stay in Starlette's Router unmodified.
- `_add_route` registers routes in `trie.add()` — no longer appends Starlette `Route` objects.
- Benchmark delta: **261k → 297k req/s total (+13%)**, DI +20%, response model +17%.

**Phase 2 — Micro-optimizations** (`feature/micro-optimizations`)
- `CompiledEndpoint` now stores `has_params` and `has_callable_deps` flags pre-computed
  at registration. Handler closure uses them to skip work at request time.
- Endpoints with no parameters skip `process_parameters()` entirely (fast-path).
- `dependency_cache = {}` only created when the endpoint actually has callable deps.
  `None` is passed otherwise; `DependencyResolver` handles it safely.
- `TachyonJSONResponse`, `TachyonBytesResponse`, and `_InternalErrorResponse` now
  pre-build both ASGI send dicts (`http.response.start` + `http.response.body`) in
  `__init__` and override `__call__` to skip the Starlette websocket-prefix check and
  background-task branch.
- Micro-benchmark delta: FULL HANDLER (no network) **1.72µs → 1.31µs (-24%)**.

**Phase 3 — Cython hot path** (`feature/cython-hotpath`)
- Optional Cython compilation for the three hottest modules:
  - `processing/compiler.pyx`: `ParamDescriptor` and `CompiledEndpoint` as `cdef class`
    (C structs — attribute access is a direct field read, not a Python dict lookup).
  - `processing/parameters.pyx`: `ParameterProcessor` with C-typed locals (`cdef int kind`,
    `cdef str name`, `cdef bint is_list`) and all sync helpers as `cdef` functions
    (zero Python frame overhead per parameter).
  - `processing/response_processor.pyx`: `ResponseProcessor` compiled to C.
- `KIND_*` constants changed from strings to integers in `compiler.py` — int comparison
  is a single machine instruction in C vs string hash+compare.
- Build system: `python setup.py build_ext --inplace` (development) or
  `pip install tachyon-api[fast]` (users).
- Falls back to `.py` automatically when `.so` is not present — zero code changes required.
- Micro-benchmark delta: `process_parameters` path+query **1.28µs → 0.82µs (-36%)**;
  FULL HANDLER **1.31µs → 1.16µs (-11%)**.

**Phase 4 — Bypass Starlette middleware stack** (`feature/phase4-5-bypass-and-trie-cython`)
- `Tachyon.__call__` now handles HTTP directly without passing through Starlette's
  `ServerErrorMiddleware` and `ExceptionMiddleware` (~1.5–2µs saving per HTTP request).
  Exception handling was already provided by the try/except in each handler closure.
- `_build_http_app()`: lazily builds an ASGI stack wrapping only user-registered
  middlewares around `_trie_dispatch`. Rebuilt automatically when `add_middleware()` is called.
- WebSocket and lifespan still delegated to Starlette's full stack unchanged.
- `scope["app"]` now set by `Tachyon.__call__` directly (previously done by Starlette).

**Phase 5 — Cython trie + Request-less fast path** (`feature/phase4-5-bypass-and-trie-cython`)
- `routing/trie.pyx`: radix trie compiled to C. `_Node` as `cdef class` (C struct fields),
  `RadixTrie` as `cdef class` with a typed `_root`. Segment matching and dict ops use
  C-level attribute access.
- `_ASGIHandler` sentinel class: endpoints with `has_params=False` and
  `has_callable_deps=False` are registered as ASGI handlers that take `(scope, receive, send)`
  directly — skipping `Request(scope, receive, send)` object creation entirely.
- `_trie_dispatch` detects `_ASGIHandler` and calls `handler.fn(scope, receive, send)`
  directly, eliminating one Python object allocation and its GC overhead per request.
- Combined F4+F5 benchmark delta: **296k → 336k req/s total (+13%)**,
  DI scenario: **39k → 47k (+20%)**, Hello World: **43k → 52k (+21%)**.

### Added
- `tachyon_api/routing/__init__.py`, `tachyon_api/routing/trie.py`: pure-Python radix trie router (fallback).
- `tachyon_api/routing/trie.pyx`: Cython-compiled trie router.
- `tachyon_api/processing/compiler.pyx`, `parameters.pyx`, `response_processor.pyx`:
  Cython extensions for the processing hot path.
- `setup.py`: build system for all Cython extensions.
- `pyproject.toml` extras: `[fast]` installs with Cython compilation; `cython` in dev deps.
- Custom X favicon (purple/pink gradient) served on Swagger UI, ReDoc, and Scalar docs.
- `ROADMAP.md` (gitignored): internal roadmap document for 10x target.

**Phase 5 remaining micro-improvements** (`feature/phase5-remaining-micro`)
- `responses.py`: `_CL_CACHE` — pre-computed content-length bytes for sizes 0–8191.
  Eliminates `str(n).encode()` on every response. `_cl_bytes()` helper used in all
  response classes.
- `routing/trie.py` + `trie.pyx`: `_EMPTY_PARAMS` singleton for static routes —
  no dict allocation per match. `_Node.allow_header` stores the pre-sorted `"GET, POST"`
  string at registration, eliminating `sorted()` + `join` on every 405 response.
- `app.py`: pre-built `_404_START`, `_404_BODY_MSG` module-level dicts — 404s send
  two pre-built ASGI messages directly without creating a `starlette.Response` object
  (~1µs saved per 404 response). 405 similarly uses `allow_header.encode()` directly.
- Micro-benchmark delta: `TachyonJSONResponse(dict)` **0.66µs → 0.62µs** (-6%);
  FULL HANDLER **1.14µs → 1.11µs** (-3%).

### Changed

- `app.py`: `Tachyon.__call__` bypasses Starlette middleware for HTTP (Phase 4).
  Adds `_build_http_app()`, `_ASGIHandler`, and fast-path ASGI handler for no-param endpoints.
- `app.py`: `add_middleware()` invalidates `_http_app` cache for lazy rebuild.
- `app.py`: HTTP routing no longer uses Starlette's Route list. `_add_route` registers
  in the trie. HTTP dispatch goes through `_trie_dispatch`; WebSocket/lifespan unchanged.
- `routing/trie.py`: `match()` now returns `allow_header: str` instead of `allowed: Set[str]`
  for `_METHOD_NOT_ALLOWED` — pre-sorted at registration time, not per-405-request.
- `responses.py`: `TachyonJSONResponse`, `TachyonBytesResponse`, `_InternalErrorResponse`
  pre-build ASGI send dicts and override `__call__` for minimal HTTP dispatch.
- `processing/compiler.py`: `KIND_*` constants changed from str to int.
- `processing/dependencies.py`: `resolve_callable_dependency` handles `cache=None`.
- `CLAUDE.md`: rewritten with minimalism/performance philosophy, opinionated design
  principles, p99 target audience, branching strategy, and changelog rule.

### Fixed

- **HF-01**: Remove mutable `_EMPTY_PARAMS` singleton from `routing/trie.py` — static routes
  now allocate a fresh `{}` per match to prevent cross-request state mutation.
- **HF-02**: Add `MANIFEST.in` and correct `pyproject.toml` includes for `.pyx` source files —
  sdist now packages all Cython source files required for compilation from source.
- **HF-04**: Wrap pre-built 404/405 ASGI dicts in `MappingProxyType` — prevents accidental
  mutation of shared module-level objects between requests.
- **HF-05**: `pyproject.toml` `[fast]` extra clarification — `pip install tachyon-api[fast]`
  installs the `cython` package but does **not** auto-compile extensions.
  Manual `python setup.py build_ext --inplace` step required after install.
- Fix `pyproject.toml` `tool.poetry.include` syntax — must be an array of objects
  (`{ path = ..., format = [...] }`), not a TOML table. Required for `python -m build`
  and PyPI upload to succeed.

### Testing

- **HF-06/07/08/10/11**: 41 new tests covering radix trie edge cases (`_EMPTY_PARAMS`,
  wildcard matching, conflicting static/param routes), fast-path dispatch for no-param
  endpoints, and 405 `Allow` header correctness.
- **97% test coverage** — 87 new tests across all modules. `.coveragerc` added with
  `[run] source`, `[report] exclude_lines` for unreachable error branches and abstract
  methods. `coverage.json` gitignored.

### Documentation

- **HF-12/13**: Migration guide translated to English (`docs/14-migration-fastapi.md`).
- **HF-14/15**: `[fast]` Cython extra documented in README and `docs/` — install steps,
  compilation requirement, fallback behavior, and per-phase benchmark impact.
- **HF-17**: `.pyx` / `.py` dual-file pattern explained — how Python auto-prefers the
  compiled `.so` over `.py` at import time; no code changes required in either mode.

---

## [1.0.0] - 2026-05-20

### Performance — 4.25x faster than FastAPI 0.136.1

This release delivers a systematic performance overhaul through endpoint pre-compilation
and accumulated micro-optimizations, bringing Tachyon from 3x to **4.25x** faster than
FastAPI across 8 real-world benchmark scenarios (262k vs 62k req/s total).

#### Endpoint Pre-Compilation (`processing/compiler.py`)
- New `compile_endpoint()` runs `inspect.signature()`, `isinstance` chains,
  `typing.get_origin/args`, alias resolution, and `msgspec.Decoder` creation **once
  at route registration**, not per request
- `CompiledEndpoint` + `ParamDescriptor` use `__slots__` for faster attribute access
- Type dispatch replaces O(n) `isinstance` chain with O(1) kind-string lookup
- `iscoroutinefunction()` cached at registration time for both endpoints and dependencies

#### Response Path
- `TachyonJSONResponse` / `TachyonBytesResponse` bypass `starlette.Response.__init__`
  (was 0.96µs) via direct `raw_headers` construction (0.27µs) — **3.5x faster**
- `Struct` payloads use `msgspec.json.encode()` directly (no `to_builtins` roundtrip)
- Pre-rendered singleton for `internal_server_error_response` — never rebuilt
- `_ORJSON_OPTS` pre-computed as module constant (was bitwise OR on every call)

#### TypeConverter
- `convert_value_bare()` / `convert_list_values_bare()` skip `unwrap_optional()` (0.54µs/param)
  since `ParamDescriptor` already stores pre-unwrapped types
- `item_is_optional` tracked separately from `is_optional` for correct `List[Optional[T]]` handling

#### Other micro-optimizations
- `__slots__` on all param marker classes (`Query`, `Path`, `Body`, `Header`, `Cookie`, `Form`, `File`)
- `__slots__` on `BackgroundTasks`; `iscoroutinefunction()` cached at `add_task()` time

### Security Fixes
- XSS: OpenAPI HTML generators now use `_safe_json()` which escapes `<`, `>`, `&`
  in script-embedded JSON (prevents `</script>` injection)
- HTTPBasic: catches `binascii.Error`, `UnicodeDecodeError`, `ValueError` specifically
  instead of bare `except Exception`

### New Features
- `Tachyon(max_body_size=10MB)` — configurable request body size limit (default 10MB);
  enforced via both `Content-Length` header and post-read byte check
- `app.register_instance(cls, instance)` / `app.get_instance(cls)` — public API for
  DI singleton cache (replaces direct `_instances_cache` access)
- `File(alias="field_name")` — file upload params now support `alias=` for multipart
  field name mapping, consistent with `Form`, `Header`, and `Cookie`
- `TypeUtils.normalize_header_name()` — centralized underscore→hyphen conversion
- Circular dependency detection in `DependencyResolver` (raises `TypeError` instead of
  infinite recursion)
- `inspect.Parameter.empty` validation before resolving unannotated injectable params
- OpenAPI generation moved to `openapi.py` — `generate_route()` on `OpenAPIGenerator`;
  `_build_param_openapi_schema` consolidated as `build_param_schema()`

### Bug Fixes
- `BackgroundTasks.__bool__` now returns `bool(self._tasks)` (was always `True`)
- `response_model=List[SomeStruct]` no longer raises `TypeError` in `issubclass()`
- `msgspec.DecodeError` (malformed JSON body) now returns 422 instead of 500
- `request.form()` and `request.body()` failures now return 422 instead of crashing
- `Body(alias=...)` and `File(alias=...)` now correctly resolve multipart field names

### Infrastructure
- `starlette` upgraded to 1.0.0 (resolves anyio 4.x incompatibility)
- `ruff` moved to dev dependencies
- `pytest.ini`: `testpaths`, `addopts` configured
- `tests/shared.py`: single source of truth for shared test models
- Exhaustive benchmark suite in `benchmark/` (FastAPI vs Tachyon, 8 scenarios)

### Testing
- **233/233 tests passing** ✅ (+10 new tests)
- New tests: circular dependency detection, `File(alias=)`, XSS escaping,
  `List[Optional[T]]` runtime, generic response model, UUID path params,
  body size edge cases, `Request` injection with default value

### Refactoring (pre-audit cleanup — 2026-05-19)
These commits were part of the cleanup sweep immediately before the security and performance
audit that led to v1.0.0:
- Stripped verbose/obvious docstrings from 35+ test files, test methods, classes, and fixtures.
  Removed docstrings that only restated the function name — code is now leaner without losing
  signal.
- Structural improvements in `app.py` and `security.py`: tightened class layout, removed
  redundant blank lines, aligned with the "less is more" style guide.
- Trimmed verbose docstrings in `HTTPAuthorizationCredentials`, `HTTPBasicCredentials`,
  `exceptions.py`, `app.middleware`, and `middlewares/core.py`.

---

## [0.9.0] - 2025-12-12

### ♻️ Refactored - Major Architecture Improvements

This release focuses on **code quality, maintainability, and separation of concerns** through systematic refactoring of the core `Tachyon` class.

#### Code Reduction
- **Reduced `app.py` from ~1157 lines to ~700 lines (-39%)** 🎯
- Extracted complex logic into dedicated, single-responsibility modules
- Improved testability and maintainability

#### New Architecture Modules

**Core Components** (`tachyon_api/core/`)
- `lifecycle.py` - Application lifecycle event management (startup/shutdown)
- `websocket.py` - WebSocket route handling and parameter injection

**Processing Components** (`tachyon_api/processing/`)
- `parameters.py` - Parameter extraction and validation (Path, Query, Body, Header, Cookie, Form, File)
- `dependencies.py` - Dependency injection resolution (injectable classes and Depends())
- `response_processor.py` - Response validation, serialization, and background task execution

#### Key Improvements
- ✅ **All 223 tests passing** - Zero regressions
- ✅ **Clean code** - Ruff linter passing on all modules
- ✅ **DRY principles** - Eliminated code duplication
- ✅ **Better separation of concerns** - Each module has a single, clear responsibility
- ✅ **Improved documentation** - All new modules fully documented
- ✅ **Type safety** - Maintained strong typing throughout

#### Technical Details
- Extracted `LifecycleManager` for managing startup/shutdown hooks and `@app.on_event` decorators
- Extracted `WebSocketManager` for WebSocket route registration and path parameter injection
- Extracted `ParameterProcessor` for all parameter types (Request, BackgroundTasks, Dependencies, Body, Query, Header, Cookie, Form, File, Path)
- Extracted `DependencyResolver` for both type-based (@injectable) and callable (Depends()) dependency injection
- Extracted `ResponseProcessor` for endpoint execution, response validation, and background task running

#### Migration Notes
- **No breaking changes** - All public APIs remain unchanged
- Internal refactoring only - fully backward compatible
- Imports remain the same: `from tachyon_api import Tachyon, Struct, Body, ...`

### Testing
- **223/223 tests passing** ✅
- All existing functionality verified
- No performance degradation

---

## [0.8.0] - 2025-12-12

### ♻️ Refactored

- **Extracted Response Processing** to `tachyon_api/processing/response_processor.py`
  - Created `ResponseProcessor` class for response handling
  - Extracted `call_endpoint()` method for endpoint execution
  - Extracted `process_response()` method for response validation and serialization
  - Handles background task execution after response
  - Validates against `response_model` if provided
  - Converts `Struct` objects to JSON-serializable dicts
  - Removed ~35 lines from `app.py`

### Testing
- **223/223 tests passing** ✅

---

## [0.7.4] - 2025-12-12

### ♻️ Refactored

- **Extracted Dependency Resolution** to `tachyon_api/processing/dependencies.py`
  - Created `DependencyResolver` class for DI resolution
  - Extracted `resolve_dependency()` for type-based (@injectable) DI
  - Extracted `resolve_callable_dependency()` for Depends() DI
  - Handles nested dependencies recursively
  - Supports dependency_overrides for testing
  - Manages singleton pattern for injectable classes
  - Removed ~130 lines from `app.py`

### Testing
- **223/223 tests passing** ✅

---

## [0.7.3] - 2025-12-12

### ♻️ Refactored

- **Extracted Parameter Processing** to `tachyon_api/processing/parameters.py`
  - Created `ParameterProcessor` class for parameter extraction
  - Extracted processing for all parameter types:
    - Request injection
    - BackgroundTasks injection
    - Dependency injection (explicit and implicit)
    - Body parameters (JSON)
    - Query parameters (single and lists)
    - Header parameters
    - Cookie parameters
    - Form parameters
    - File uploads
    - Path parameters (explicit and implicit)
  - Removed ~331 lines from `app.py`

### Testing
- **223/223 tests passing** ✅

---

## [0.7.2] - 2025-12-12

### ♻️ Refactored

- **Extracted WebSocket Handling** to `tachyon_api/core/websocket.py`
  - Created `WebSocketManager` class for WebSocket route management
  - Extracted `websocket_decorator()` method
  - Extracted `add_websocket_route()` method
  - Handles path parameter injection for WebSocket routes
  - Removed ~37 lines from `app.py`

### Testing
- **223/223 tests passing** ✅

---

## [0.7.1] - 2025-12-12

### ♻️ Refactored

- **Extracted Lifecycle Management** to `tachyon_api/core/lifecycle.py`
  - Created `LifecycleManager` class for lifecycle event management
  - Extracted `create_combined_lifespan()` method
  - Extracted `on_event_decorator()` method
  - Manages both `@app.on_event` decorators and context manager lifespans
  - Removed ~55 lines from `app.py`

### Testing
- **223/223 tests passing** ✅

---

## [0.7.0] - 2025-12-12

### Added

- **WebSocket Support**: Real-time bidirectional communication
  - `@app.websocket(path)` decorator for WebSocket endpoints
  - `@router.websocket(path)` for WebSocket routes in routers
  - Path and query parameter support in WebSocket routes
  - Text, JSON, and binary message handling
  - Automatic injection of WebSocket object into handler functions

- **Complete Documentation**: 16 comprehensive guides in `docs/`
  - Getting Started, Architecture, Dependency Injection
  - Parameters, Validation, Security
  - Caching, Lifecycle Events, Background Tasks
  - WebSockets, Testing, CLI Tools
  - Request Lifecycle, FastAPI Migration, Best Practices

- **KYC Demo Example**: Production-ready example in `example/`
  - Complete Know Your Customer verification system
  - JWT authentication with `@injectable` services
  - Customer CRUD with clean architecture
  - Document uploads with validation
  - Background task processing for verification
  - WebSocket notifications for real-time updates
  - 12 tests demonstrating mocking and dependency overrides

### Changed

- Example project completely rewritten from simple CRUD to comprehensive KYC system
- README updated with feature matrix and documentation links
- Version badge updated to 0.7.0

### Tests

- 12 new tests for WebSockets (223 → 235 total)
  - Basic echo, JSON/binary messages, path/query params
  - Router integration, multiple routes, disconnect handling
- 12 new tests for KYC example
  - Authentication, customers, verification modules

---

## [0.6.7] - 2025-12-12

### Added

- **Testing Utilities**: Comprehensive testing support
  - `TachyonTestClient`: Synchronous test client wrapping `starlette.testclient.TestClient`
  - `AsyncTachyonTestClient`: Asynchronous test client with `httpx.AsyncClient` and `ASGITransport`
  - `app.dependency_overrides`: Dictionary for mocking dependencies in tests
  - Supports overriding `@injectable` classes and `Depends()` callables

### Tests

- 12 new tests for testing utilities (211 → 223 total)
  - TachyonTestClient (GET/POST, headers, query, cookies, context manager)
  - AsyncTachyonTestClient (async GET/POST)
  - dependency_overrides (classes, callables, lambdas, multiple overrides)

---

## [0.6.6] - 2025-12-12

### Added

- **CLI Tools**: NestJS-inspired command-line interface
  - `tachyon new <project>`: Scaffold new project with clean architecture
  - `tachyon generate service <name>`: Generate complete module (controller, service, repository, dto, tests)
  - `tachyon generate controller/repository/dto`: Generate individual components
  - `tachyon openapi export`: Export OpenAPI schema to JSON
  - `tachyon openapi validate`: Validate OpenAPI schema files
  - `tachyon lint check/fix/format/all`: Code quality tools (ruff wrapper)
  - Project scaffolding includes: app.py, config.py, modules/, shared/, tests/
  - `--crud` flag for generating CRUD operations
  - `--no-tests` flag to skip test generation

### Changed

- Added `[tool.poetry.scripts]` entry point: `tachyon = "tachyon_api.cli:app"`

### Tests

- 13 new tests for CLI (198 → 211 total)
  - Project creation, existing directory handling
  - Service generation (basic, CRUD, no-tests, individual components)
  - Kebab-case conversion (user-profile → user_profile)
  - Version command, lint check, openapi validate

---

## [0.6.5] - 2025-12-12

### Added

- **Background Tasks**: Fire-and-forget task execution after response
  - `BackgroundTasks` class with `add_task(func, *args, **kwargs)` method
  - Automatic injection when `background_tasks: BackgroundTasks` parameter present
  - Supports sync and async functions
  - Error handling: failed tasks don't affect response
  - Tasks execute in order after response is sent

### Tests

- 6 new tests for background tasks (192 → 198 total)
  - Basic sync/async tasks
  - Multiple tasks, keyword arguments
  - Coexistence with other parameters
  - Error handling in tasks

---

## [0.6.4] - 2025-12-12

### Added

- **Security Foundation**: Authentication and authorization schemes
  - `HTTPBearer`: Extract Bearer token from Authorization header
  - `HTTPBasic`: Extract and decode Basic auth credentials
  - `OAuth2PasswordBearer`: OAuth2 password flow with configurable token URL
  - `APIKeyHeader`, `APIKeyQuery`, `APIKeyCookie`: API key extraction
  - All schemes support `auto_error=False` for optional authentication
  - Credential classes: `HTTPAuthorizationCredentials`, `HTTPBasicCredentials`
  - All security schemes are callable dependencies compatible with `Depends()`

### Tests

- 12 new tests for security (180 → 192 total)
  - HTTPBearer (valid/missing/invalid token, auto_error=False)
  - HTTPBasic (valid/missing credentials, base64 decoding)
  - API Keys (header, query, cookie)
  - OAuth2PasswordBearer (valid/missing token)

---

## [0.6.3] - 2025-12-12

### Added

- **Exception Handling System**: Custom exceptions and handlers
  - `HTTPException` class with `status_code`, `detail`, and optional `headers`
  - `@app.exception_handler(ExceptionClass)` decorator for custom handlers
  - Supports sync and async exception handlers
  - Request object injection in handlers via `request: Request` parameter
  - Multiple exception handlers for different exception types
  - Allows overriding default `HTTPException` handler

### Tests

- 11 new tests for exception handling (169 → 180 total)
  - Basic HTTPException (401, 403, 500, custom headers)
  - Custom exception handler decorator
  - Sync/async handlers
  - Request injection into handlers
  - Multiple handlers, overriding HTTPException handler
  - Unhandled exceptions fallback

---

## [0.6.2] - 2025-12-12

### Added

- **File Handling**: Form data and file uploads
  - `Form()` parameter marker for `application/x-www-form-urlencoded` data
  - `File()` parameter marker for `multipart/form-data` uploads
  - `UploadFile` class wrapping Starlette's UploadFile
  - Support for multiple file uploads (List[UploadFile])
  - Mixed form data and file uploads in same endpoint
  - Async file operations (read, seek, close)
  - Dependency: `python-multipart` for form parsing

### Tests

- 8 new tests for file handling (161 → 169 total)
  - Form data parsing (single, multiple fields)
  - File uploads (single, multiple, optional)
  - Mixed form + file
  - UploadFile properties (filename, content_type, size)

---

## [0.6.1] - 2025-12-12

### Added

- **Lifecycle Events**: Application startup and shutdown hooks
  - `lifespan` context manager parameter in `Tachyon.__init__`
  - `@app.on_event("startup")` decorator for startup tasks
  - `@app.on_event("shutdown")` decorator for shutdown tasks
  - Supports both sync and async event handlers
  - `app.state` for storing application-wide state
  - Combined lifespan merging decorator-based and context manager events

### Tests

- 17 new tests for lifecycle (144 → 161 total)
  - Lifespan context manager (startup/shutdown execution)
  - on_event decorators (sync/async)
  - app.state usage
  - Combined lifespan + on_event
  - Execution order verification

---

## [0.6.0] - 2025-12-11

### Added

- **Request Injection**: Endpoints can now receive the Starlette `Request` object by annotating a parameter with `request: Request`
  - Access to headers, query params, cookies, client info, and raw request data
  - Works alongside other parameter types (Query, Path, Body, etc.)

- **Header() Parameter Marker**: Extract values from HTTP request headers
  - Required headers: `Header(...)` returns 422 if missing
  - Optional with default: `Header("default-value")`
  - Case-insensitive matching (HTTP standard)
  - Underscore-to-hyphen conversion: `x_request_id` matches `X-Request-Id`
  - Custom header names with alias: `Header(..., alias="X-Auth-Token")`
  - Full OpenAPI schema generation for header parameters

- **Cookie() Parameter Marker**: Extract values from HTTP cookies
  - Required cookies: `Cookie(...)` returns 422 if missing
  - Optional with default: `Cookie("default-value")`
  - Custom cookie names with alias: `Cookie(..., alias="session_token")`
  - Full OpenAPI schema generation for cookie parameters

- **Depends(callable) - Factory Dependencies**: Enhanced dependency injection
  - Sync function dependencies: `Depends(get_db_connection)`
  - Async function dependencies: `Depends(get_current_user_async)`
  - Lambda dependencies: `Depends(lambda: {"config": "value"})`
  - Nested dependencies: callables can have their own `Depends()` parameters
  - Per-request caching: same callable called once per request
  - Works alongside existing `Depends()` type-based resolution

### Changed

- **Refactored Type Utilities**: Centralized type handling to reduce code duplication
  - `OPENAPI_TYPE_MAP` in `type_utils.py` as single source of truth
  - `TypeUtils.get_openapi_type()` for type-to-schema conversion
  - Removed duplicate `_unwrap_optional` and `TYPE_MAP` from `openapi.py`
  - Removed dead code: `_generate_schema_for_struct`

### Tests

- 25 new tests (119 → 144 total)
  - `test_request_injection.py`: 5 tests
  - `test_header_params.py`: 8 tests
  - `test_cookie_params.py`: 5 tests
  - `test_depends_callable.py`: 7 tests

---

## [0.5.9] - 2025-09-04

### Added

- Tests: new utility test suite in `tests/test_utils.py`
  - TypeUtils: `unwrap_optional`, `is_list_type`, `get_type_name`
  - TypeConverter: `convert_value` (str, int, bool, Optional) and `convert_list_values` (including Optional items)
  - Error mapping verification: 422 for invalid query values and 404 for invalid path values

### Changed

- Refactor: extracted and modularized utility helpers previously located in `app.py`
  - New modules: `tachyon_api/utils/type_utils.py` and `tachyon_api/utils/type_converter.py`
  - No intended runtime behavior changes; improves separation of concerns and reuse

---

## [0.5.8] - 2025-08-26

### Added

- Global Exception Handler: structured 500 responses for unhandled exceptions
  - Returns `{ "success": false, "error": "Internal Server Error", "code": "INTERNAL_SERVER_ERROR" }`
  - Prevents leaking internal exception details to clients
- Tests: Added `test_global_unhandled_exception_is_structured_500` (TDD)
- Documentation: README updated (error section) and example endpoint `/error-demo`

---

## [0.5.7] - 2025-08-26

### Added

- Response Model Validation: `response_model` in route decorators to enforce and serialize outputs via msgspec
  - Converts handler payloads to the specified Struct type; 500 on response validation error
  - OpenAPI 200 response schema references the Struct component
- OpenAPI Parameters: Enhanced schema generation for Optional and List parameter types
  - Optional[T] → `nullable: true` on the base type schema
  - List[T] → `type: array` with proper `items` schema in both query and path parameters
  - List[Optional[T]] → `items.nullable: true`
- Default JSON Response: `TachyonJSONResponse` is now used by default for dict/Struct payloads
  - orjson-based, supports UUID, date, datetime and msgspec Struct out of the box
- Deep OpenAPI Schemas for Struct
  - Nested Struct components auto-registered and referenced
  - Field Optional/List handling with `nullable` and `array/items`
  - Type formats for `uuid` and `date-time`/`date`
- Standard Error Schemas in OpenAPI
  - 422 Validation Error → `#/components/schemas/ValidationErrorResponse`
  - 500 Response Validation Error → `#/components/schemas/ResponseValidationError`

### Changed

- Error Format Unification: standardized error payloads for validation and response errors
  - 422 (request validation) → `{ "success": false, "error": "...", "code": "VALIDATION_ERROR" }`
  - 500 (response_model validation) → `{ "success": false, "error": "Response validation error: ...", "detail": "...", "code": "RESPONSE_VALIDATION_ERROR" }`

### Fixed

- Query list parsing accepts both CSV (`?ids=1,2,3`) and repeated params (`?ids=1&ids=2`)
- Runtime support for `List[Optional[T]]` in Query and Path
  - Empty string "" and literal "null" are treated as `None` when item type is Optional

### Example

- Added `/api/v1/users/e2e` endpoint demonstrating end-to-end safety (Body + response_model), unified errors, and deep OpenAPI schemas.

---

## [0.5.6] - 2025-08-26

### Added

- Cache Decorator with TTL (`tachyon_api.cache.cache`)
  - Works with sync and async functions, including route handlers
  - Global, app-level configuration via `create_cache_config()` and `Tachyon(cache_config=...)`
  - Pluggable backends: `InMemoryCacheBackend` (default), `RedisCacheBackend`, `MemcachedCacheBackend`
  - Customizable `key_builder` and `unless` predicate
- Tests: New `tests/test_cache_decorator.py` validating caching behavior, TTL, async support, and config integration
- Example: Added cached endpoint `/cached/time` and cache configuration in `example/app.py`

### Changed

- App: `Tachyon` now accepts `cache_config` and applies it on initialization (backwards compatible)
- Documentation: README updated with cache section, quick start, configuration, and backend usage
- Language Consistency: Standardized remaining comments/docstrings to English across touched files

### Notes

- Redis/Memcached backends are lightweight adapters; bring your own client instance. No hard dependencies added.

---

## [0.5.5] - 2025-08-12

### Added

- Built-in Middlewares: CORSMiddleware and LoggerMiddleware
  - Standard ASGI-compatible classes usable via `app.add_middleware(...)`
  - CORS: preflight handling, allow/expose headers, credentials, max-age
  - Logger: request start/end, duration, status; optional headers and body preview with redaction
- Tests: Added `tests/test_cors_middleware.py` and `tests/test_logger_middleware.py`
- Example: Integrated built-in middlewares in `example/app.py`

### Changed

- Middleware Refactor: centralized integration helpers in `tachyon_api/middlewares/core.py`
  - `apply_middleware_to_router()` for Starlette stack integration
  - `create_decorated_middleware_class()` for decorator-based middlewares
  - Maintained full backward compatibility for `app.add_middleware` and `@app.middleware()`
- Language Consistency: standardize docstrings and comments to English in middleware modules and tests
- Documentation: README updated with built-in middleware usage and example details

---

## [0.5.4] - 2025-08-06

### Added

- **Comprehensive README**: Created a detailed README.md for the project.
  - Comprehensive feature overview and code examples
  - Clear installation instructions for the beta version
  - Feature comparison with FastAPI
  - Detailed examples of dependency injection and middleware usage
  - Expanded roadmap with upcoming features
  - Contributor guidelines and project structure explanation

### Technical Improvements

- **Project Documentation**: Enhanced project presentation for the upcoming GitHub beta release
- **Onboarding Experience**: Clearer instructions for new users and contributors
- **Framework Positioning**: Better articulation of Tachyon API's unique value proposition

---

## [0.5.3] - 2025-08-06

### Added

- **Traditional Python Environment Support:** Added requirements.txt for broader compatibility.
  - Support for traditional venv-based workflows alongside Poetry
  - Direct pip installation capability via `pip install -r requirements.txt`
  - Maintained synchronization between Poetry dependencies and requirements.txt

### Technical Improvements

- **Deployment Flexibility:** Support for environments where Poetry isn't available
- **CI/CD Compatibility:** Better integration with common CI/CD pipelines
- **Onboarding Experience:** Easier project setup for developers familiar with traditional Python workflows

---

## [0.5.2] - 2025-08-06

### Changed

- **Decoupled Test Architecture:** Refactored all tests to be self-contained.
  - Removed test dependencies on conftest.py fixture for better isolation
  - Each test now creates its own Tachyon instance with required configuration
  - Improved test clarity and maintenance by making test dependencies explicit
  - Fixed language consistency across all test files (standardized to English)

### Fixed

- **Response Module:** Added missing HTMLResponse export in responses.py
  - Resolved issue with TestStarletteCompatibility.test_starlette_imports_available test
  - Ensured proper re-export of all Starlette response types for convenience

### Technical Improvements

- **Testing Efficiency:** Self-contained tests provide better failure isolation and debugging
- **Test Clarity:** Each test file now clearly shows its dependencies and requirements
- **Consistent Documentation:** All code comments and docstrings standardized to English

---

## [0.5.1] - 2025-08-06

### Added

- **Example Middleware Implementation:** Enhanced example application with middleware examples.
  - Added request logging middleware to demonstrate request/response monitoring
  - Implemented response headers middleware to show response modification
  - Created a reusable middleware setup pattern in a dedicated module

### Technical Improvements

- **Middleware Organization:** Implemented a clean pattern for middleware definition in separate files
- **Middleware Documentation:** Comprehensive examples demonstrating middleware capabilities
- **Example Architecture:** Improved example application structure with middleware integration

---

## [0.5.0] - 2025-08-06

### Added

- **Middleware Support:** Added comprehensive middleware functionality.
  - Implemented `app.add_middleware()` method for adding middleware classes
  - Created `@app.middleware()` decorator for a more elegant middleware definition
  - Added support for both class-based and decorator-based middleware approaches
  - Full integration with the ASGI specification for compatibility with standard patterns

### Changed

- **Decorator API:** Enhanced the API with middleware decorators for better developer experience
  - Consistent pattern with route decorators like `@app.get()`, `@app.post()`, etc.
  - Support for middleware type filtering (`http`, etc.)

### Technical Improvements

- **Request/Response Pipeline:** Complete implementation of the middleware "onion" pattern
- **Testing Coverage:** Comprehensive test suite for middleware functionality
- **Architecture Flexibility:** Support for multiple middleware implementation styles

---

## [0.4.3] - 2025-08-06

### Added

- **orjson Integration:** Enhanced JSON processing with high-performance orjson library.
  - Added new `encode_json` and `decode_json` functions for direct access to optimized JSON operations
  - Implemented seamless serialization of complex types (UUID, datetime, etc.)
  - Maintained full backward compatibility with existing Struct-based models
  - Comprehensive test suite ensures correctness and performance improvements

### Technical Improvements

- **Performance Optimization:** JSON serialization/deserialization now significantly faster with orjson
- **Enhanced Type Support:** Better handling of complex types like UUID, datetime, and nested Struct objects
- **Flexible Configuration:** Support for orjson-specific options when using the explicit API

---

## [0.4.2] - 2025-08-06

### Fixed

- **OpenAPI Documentation:** Fixed Scalar API Reference implementation.
  - Resolved issue where the Scalar UI failed to load properly at the `/docs` endpoint
  - Improved HTML structure of documentation to remove malformed elements
  - Fixed Scalar script URL to ensure proper component loading

### Added

- **Documentation Testing:** New unit test to verify proper HTML generation for Scalar API Reference.
  - Implemented `test_scalar_html_generation()` that validates the correct structure of generated HTML
  - Ensures compatibility between all three documentation interfaces: Scalar (default), Swagger UI, and ReDoc

### Technical Improvements

- **Documentation Consistency:** Ensured consistency between all three available documentation interfaces
  - Scalar API Reference: available at `/docs` (default)
  - Swagger UI: maintains compatibility for integration with existing tools
  - ReDoc: available as an alternative at `/redoc`

---

## [0.4.1] - 2025-08-05

### Changed

- **Example Application Refactoring:** Complete reorganization of the example application using clean architecture principles.
  - Restructured `/example` directory with proper separation of concerns
  - Added `/example/routers/` directory for organized API endpoint management
  - Enhanced `/example/repositories/` with proper dependency injection setup
  - Improved `/example/services/` to demonstrate implicit dependency injection
  - Updated `/example/models/` with comprehensive data structures

### Added

- **Router Organization:** New router-based architecture in example application.
  - `users_router`: Complete user management endpoints (`/api/v1/users/*`)
  - `items_router`: Item management endpoints (`/api/v1/items/*`)
  - `admin_router`: Administrative endpoints (`/admin/*`)

### Technical Improvements

- **Clean Architecture Demonstration:** Example now showcases proper layered architecture:
  - Models: Data structures and validation
  - Repositories: Data access layer with `@injectable` decorators
  - Services: Business logic layer with automatic dependency resolution
  - Routers: API endpoint organization with implicit dependency injection
- **Enhanced Documentation:** Updated example application with comprehensive inline documentation
- **Implicit Dependency Injection:** Example demonstrates parameter ordering for maximum use of implicit DI

---

## [0.4.0] - 2025-08-05

### Added

- **Router System:** Complete route grouping functionality similar to FastAPI's APIRouter.
  - Create routers with common prefixes, tags, and dependencies
  - Include multiple routers in the main application with `app.include_router()`
  - Automatic prefix application to all routes in a router
  - Tag inheritance from router to individual routes
  - Full compatibility with existing parameter types (Query, Path, Body) and dependency injection
  - OpenAPI integration with proper route documentation

- **Scalar API Reference Integration:** Modern API documentation interface as default.
  - `/docs` now serves Scalar API Reference (modern, fast UI)
  - `/swagger` continues to serve Swagger UI (legacy support)
  - `/redoc` unchanged, continues to serve ReDoc
  - Configurable Scalar CDN URLs and styling options
  - Backward compatibility maintained for all existing OpenAPI configurations

### Changed

- **Documentation Default:** `/docs` endpoint now uses Scalar instead of Swagger UI by default
- **Route Organization:** Enhanced route organization capabilities with Router system

### Technical Details

- Router implementation follows TDD approach with comprehensive test coverage
- Zero code redundancy - Router reuses existing Tachyon routing logic
- 100% backward compatibility with existing applications
- Router stores route definitions and delegates actual routing to main Tachyon app

---

## [0.3.1] - 2025-08-04

### Added

- **Complete Example Application:** A full example project has been added in the `/example` directory.
- The example demonstrates a real-world use case with a complete `users` service, showcasing:
    - The recommended project structure.
    - Usage of the Service and Repository patterns.
    - Implementation of various endpoints using `@Body`, `@Query`, `@Path`, and Dependency Injection.
- This application serves as a reference for new users and as a basis for tutorials and training materials.

---

## [0.3.0] - 2025-08-04

### Added

- **Structured Response Helpers:** A new `responses.py` module was introduced to provide a consistent API output
  structure.
    - Includes `success_response` for standardized success payloads (`{"success": true, "data": ..., "message": ...}`).
    - Includes `error_response`, `not_found_response`, `conflict_response`, and `validation_error_response` for
      standardized error payloads.
- **Centralized Starlette Responses:** Re-exported core `starlette.responses` (`JSONResponse`, `HTMLResponse`) from
  `tachyon_api.responses` to centralize imports for the end-user.

---

## [0.2.1] - 2025-08-04

### Added

- **Parameter Documentation:** The `Query()` and `Path()` parameter markers now accept a `description` argument.
- **Enhanced OpenAPI Generation:** The OpenAPI schema generator now includes these descriptions, leading to richer and
  more descriptive API documentation.

---

## [0.2.0] - 2025-08-04

### Added

- **Automatic OpenAPI 3.0 Schema Generation:** The framework now introspects routes, parameters (`Path`, `Query`,
  `Body`), and models (`Struct`) to generate a compliant `openapi.json`.
- **Interactive API Documentation:** Added a `/docs` endpoint that serves a fully interactive Swagger UI.
- `include_in_schema` option for routes to exclude specific endpoints from the OpenAPI documentation.

---

## [0.1.0] - 2025-07-28

### Added

- **Dependency Injection System:**
    - `@injectable` decorator to register classes with the DI container.
    - Hybrid injection support for endpoints:
        - Implicitly for parameters with a registered type hint and no default value.
        - Explicitly via a `Depends()` marker for FastAPI compatibility and clarity.
    - Constructor injection for nested dependencies within `@injectable` classes.
- **Parameter Validation & Extraction:**
    - `@Body()` decorator for request body validation using `msgspec.Struct`.
    - `@Query()` decorator for query parameter extraction, type conversion, and validation (required and default
      values).
    - `@Path()` decorator for path parameter extraction and type conversion.
- **Centralized Test Fixture:** A project-wide `app` fixture in `conftest.py` to streamline testing.

### Changed

- Refactored parameter resolution logic out of the main request handler into dedicated helper functions for improved
  maintainability.

---

## [0.0.1] - 2025-07-21

### Added

- **Core Application:** Initial `Tachyon` ASGI application class.
- **Dynamic Routing:** Support for all standard HTTP methods (`GET`, `POST`, `PUT`, `DELETE`, etc.) via dynamic
  decorator generation.
- **Basic Project Structure:** Initial setup using Poetry.
- **Testing Foundation:** Integrated `pytest` and `httpx` for Test-Driven Development.
- **Code Quality:** Integrated `ruff` for code linting and formatting.
- **Model Abstraction:** Re-exported `msgspec.Struct` as `tachyon_api.models.Struct` to create a stable public API for
  users.