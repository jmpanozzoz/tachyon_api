# Cython Plan v1.2.9 — Impact Analysis & Sprint Roadmap

**Date:** 2026-05-22
**Status of input:** built on `docs/audit-v1.2.83.md` baseline.
**Output:** ordered, quantified plan of modules to compile in v1.2.9.

---

## 1. State of compilation today

`setup.py build_ext --inplace` compiles 7 extensions:

| `.pyx` source | Compiled `.so` | Role | Status |
|---|---|---|---|
| `routing/trie.pyx` | `routing/trie.cpython-*.so` | Radix trie | ✅ cdef class, mature |
| `processing/compiler.pyx` | `processing/compiler.cpython-*.so` | Endpoint pre-compile | ✅ cdef class, mature |
| `processing/parameters.pyx` | `processing/parameters.cpython-*.so` | Request param extraction | ⚠️ **diverged** — see §1.1 |
| `processing/response_processor.pyx` | `…response_processor.cpython-*.so` | Response coercion | ✅ cdef class, mature |
| `processing/scope.pyx` | `…scope.cpython-*.so` | Lazy `Request` wrapper | ✅ cdef class, mature |
| `processing/dispatch.pyx` | `…dispatch.cpython-*.so` | Trie-call dispatcher | ✅ cdef class, mature |
| `_server_fast.pyx` | `_server_fast.cpython-*.so` | Direct `transport.write()` | ✅ cdef class, mature |

Everything else in `tachyon_api/` is pure-Python.  When `.so` files are
present Python prefers them; when absent it falls back to the `.py`
sibling (or the package version).

### 1.1 The `parameters.pyx` divergence (load-bearing for v1.2.9)

**Problem.**  In v1.2.2 we split `parameters.py` into a thin orchestrator
plus **10 atomic extractors under `processing/_extractors/`** (`body.py`,
`query.py`, etc.).  The Cython companion `parameters.pyx` was not
re-organised — it still contains the pre-v1.2.2 monolithic logic.

**Consequence at runtime today**:
- **Compiled mode (production)**: imports load `parameters.cpython-*.so`,
  which executes the **monolithic v1.2.0 body of code**.  The 10 atomic
  `_extractors/*.py` modules are dead weight — never touched.  This is
  why `coverage.py` reports 0% on `_extractors/` (audit §1).
- **Pure-Python fallback**: `parameters.py` (the modular orchestrator)
  delegates to the 10 atomic extractors as designed.

**Implication for v1.2.9.**  Any cdef-ification of the atomic extractors
**only helps the pure-Python fallback** unless we also restructure
`parameters.pyx` to delegate to compiled `_extractors/*.pyx` siblings.
That restructuring is one of v1.2.9's biggest deliverables — and the
biggest single risk for regression.

Two viable shapes for v1.2.9:

| Shape | What | Pros | Cons |
|---|---|---|---|
| **A — Mirror SRP in Cython** | One `.pyx` per atomic module under `_extractors/`. `parameters.pyx` becomes a thin orchestrator that imports cdef extractors. | True SRP across both modes; per-extractor optimisation; tests directly target the cdef extractor classes. | 10 extra `.so` files (import overhead at startup); duplicated maintenance. |
| **B — Keep monolithic parameters.pyx, embed extractor logic** | Re-implement each extractor as a private `cdef class` inside `parameters.pyx`; matches the .py orchestrator at the function-level only. | Single `.so`; lowest import overhead; closest to current. | Cython file becomes ~600 lines; SRP exists only in .py. |

**Recommendation: Shape A in stages, with a perf gate.**  Compile the atomic
extractors in priority order (see §4) and *measure each step*.  If the
import-overhead penalty makes Shape A slower than Shape B at any point,
fall back to Shape B for the remaining extractors.  We can measure this
because compiler.py / parameters.py + 5 already-compiled extensions give
us a known good `.so` count baseline.

---

## 2. Classification of all 63 SRP modules

Path frequency is sampled against an idealised "endpoint with one Body
+ one Depends class + JSON response" request:

- **Hot** = touched on every request (or every request matching the path's
  feature, e.g. body-having for body extractor).
- **Lukewarm** = touched when a feature is in use (auth header, WS upgrade).
- **Cold** = startup-only or admin-only (CLI, OpenAPI HTML render).

cdef feasibility:
- **Easy** = sync, typed attributes, pure functions, no `await`, no isinstance ladders.
- **Medium** = sync but with isinstance dispatch on user types, or limited closures.
- **Hard** = async with shared state, or requires `nogil` plus careful object lifetime.
- **N/A** = cold path, no perf relevance.

### 2.1 `app/` (13 modules — Tachyon facade + collaborators)

| Module | Path | Compiled? | cdef feasibility | Notes |
|---|---|---|---|---|
| `__init__.py` (Tachyon facade) | hot (per request via `__call__`) | no | Medium | Heavy `__init__` (cold); `__call__` delegates to `_asgi_entry`. |
| `_asgi_entry.py` | hot | no | Easy | Thin: sets `scope["app"]`, builds `_http_app` lazily. |
| `_http_dispatch.py` | hot | no | Easy | One `if scope["type"] == "http"`. |
| `_asgi_handler.py` | hot | no | Easy | One-attribute marker class. |
| `_exception_table.py` | lukewarm | no | Easy | Walks `_handlers` dict; isinstance per entry. |
| `_handler_factory.py` | **factory cold, generated closure hot** | no | Medium | The closure does dict allocation + 3 await branches. |
| `_fast_asgi_factory.py` | **factory cold, generated closure hot** | no | Medium | Closure includes `_tachyon_direct_write` fast path. |
| `_route_installer.py` | cold (startup) | no | N/A | |
| `_registry.py` | cold | no | N/A | |
| `_mw_stack.py` | cold | no | N/A | Build called lazily on first req but stable thereafter. |
| `_docs_routes.py` / `_docs_schemas.py` | cold | no | N/A | |
| `_404.py` / `_405.py` | hot constants | no | N/A | Already module-level constants; nothing to compile. |

### 2.2 `processing/` (request hot path)

| Module | Path | Compiled? | cdef feasibility | Notes |
|---|---|---|---|---|
| `parameters.{py,pyx}` | hot | ⚠️ diverged | Medium | Monolithic `.pyx` vs modular `.py` (see §1.1). |
| `compiler.{py,pyx}` | cold (startup) | yes | — | Already cdef. |
| `response_processor.{py,pyx}` | hot | yes | — | Already cdef. |
| `scope.{py,pyx}` | hot | yes | — | Already cdef. |
| `dispatch.{py,pyx}` | hot | yes | — | Already cdef. |
| `_extractors/_base.py` (`ExtractorResult`) | hot | no | Easy | `NamedTuple`; trivial. |
| `_extractors/_missing.py` | hot (missing-param path) | no | Easy | One function, ≤ 6 lines. |
| `_extractors/body_limit.py` | hot (body requests) | no | Easy | Pure size-check. |
| `_extractors/body.py` | hot (body requests) | no | Medium | Calls msgspec; mostly C already. Gain limited to non-msgspec overhead. |
| `_extractors/query.py` | hot (query params) | no | Easy | Single lookup + TypeConverter. |
| `_extractors/query_list.py` | hot | no | Medium | CSV split + per-item convert. |
| `_extractors/header.py` | hot (header params) | no | Easy | One header dict lookup. |
| `_extractors/cookie.py` | hot (cookie params) | no | Easy | One cookie dict lookup. |
| `_extractors/form.py` | lukewarm (multipart) | no | Easy | One form-data lookup. |
| `_extractors/file.py` | lukewarm (multipart) | no | Easy | hasattr check + value return. |
| `_extractors/path.py` | hot (path params) | no | Easy | Null-byte check + TypeConverter. |
| `dependencies/_sig_cache.py` | warm (DI requests) | no | Easy | dict.get + inspect.signature cache. |
| `dependencies/_override_lookup.py` | warm | no | Easy | dict lookup + callable invocation. |
| `dependencies/_scope_cache.py` | warm (DI requests) | no | Easy | Two conditional branches. |
| `dependencies/_circular_detector.py` | warm | no | Easy | Set add/remove. |
| `dependencies/_class_factory.py` | warm (DI requests) | no | Medium | Iterates sig.parameters → recursive resolve. |
| `dependencies/_callable_factory.py` | warm (callable DI) | no | **Hard** | async + iscoroutine check + nested resolve. |
| `dependencies/_resolver.py` | warm | no | Medium | Pipeline coordinator. |

### 2.3 `responses/` (10 atomic modules)

| Module | Path | Compiled? | cdef feasibility | Notes |
|---|---|---|---|---|
| `_json_response.py` (`TachyonJSONResponse`) | hot (every JSON response) | no | Easy | Inherits Starlette's `JSONResponse`; bypasses `__init__`. cdef class on top of a Python parent is fully supported by Cython. |
| `_bytes_response.py` (`TachyonBytesResponse`) | hot (every Struct response) | no | Easy | Same shape as `_json_response`. |
| `_internal_error.py` (`_InternalErrorResponse`) | lukewarm (errors) | no | Easy | Singleton; constructed once. |
| `_caches.py` | hot constants | no | N/A | Module-level dicts. |
| `_constants.py` | hot constants | no | N/A | |
| `_wire.py` | hot (only when `TachyonServer` direct-write path) | no | N/A | Constants for `_server_fast.pyx`. |
| `_success.py` / `_error.py` / `_validation.py` | lukewarm (helpers) | no | Easy | Build a dict and instantiate response. Compile only if response classes compile. |

### 2.4 `openapi/` (13 modules — all cold)

| Module | Path | Compiled? | cdef feasibility | Notes |
|---|---|---|---|---|
| All 13 modules | cold (startup + `/openapi.json` + `/docs`) | no | N/A | No Cython migration. |

### 2.5 `security/` (11 modules — lukewarm at most)

| Module | Path | Compiled? | cdef feasibility | Notes |
|---|---|---|---|---|
| `_bearer_parser.py` (`parse_bearer_header`) | lukewarm (only when bearer is used) | no | **Easy + `nogil`** | Pure string parsing — direct memchr candidate. |
| Auth scheme classes | lukewarm | no | N/A | Bottleneck is `request.headers.get(...)`, already C in Starlette. |

### 2.6 Other modules

| Module | Path | Compiled? | cdef feasibility | Notes |
|---|---|---|---|---|
| `core/websocket.py` (`WebSocketManager`) | cold for HTTP; lukewarm per connection | no | Medium | Pre-compute at registration is cold; per-connection inject + path conversion is lukewarm. |
| `core/lifecycle.py` | cold (startup/shutdown) | no | N/A | |
| `routing/trie.{py,pyx}` | hot | yes | — | Already cdef. |
| `middlewares/cors.py` / `logger.py` / `security_headers.py` | lukewarm (per req only if mounted) | no | Medium | Per-request `send` wrappers; cdef-iable but middleware is user-opt-in. Defer. |
| `cache.py` | lukewarm (when `@cache` is used) | no | Easy | Backends are user-supplied; the decorator itself is small. |
| `background.py` | lukewarm | no | Easy | Tiny class. |
| `di.py` | startup | no | N/A | Decorator + registry only. |
| `models.py` / `params.py` / `exceptions.py` / `files.py` | startup | no | N/A | Markers/value types. |
| `cli/` | admin | no | N/A | |

---

## 3. Per-module impact estimates

Estimates anchored on the v1.2.83 baseline (1.07 µs FULL HANDLER median,
compiled).  Approach:

1. The "Tachyon overhead minus already-compiled stages" is roughly
   `1.07 µs − 0.80 (body extract) − 0.13 (msgspec encode) − 0.05 (await) ≈ 0.09 µs`
   spread across all *non-compiled* pure-Python orchestration: handler closure,
   exception table, scope dict allocation, etc.
2. Compiling a pure-Python class that already has `__slots__` typically yields
   **5 – 15%** on its own method bodies.
3. Compiling a small pure function with no GIL needs (`parse_bearer_header`,
   `_missing`) can reach **30 – 50%**, but the absolute savings are small.

### 3.1 Highest expected impact (do first)

| Module | Path frequency | Best-case gain on FULL HANDLER | Notes |
|---|---|---:|---|
| `responses/_json_response.py` (cdef class) | every JSON response | **−0.04 to −0.07 µs** | Two `await send()` plus header list build; cdef removes attribute-access cost. |
| `responses/_bytes_response.py` (cdef class) | every Struct response | **−0.04 to −0.07 µs** | Same shape as `_json_response`. |
| `processing/dependencies/_resolver.py` + `_class_factory.py` + `_scope_cache.py` (cdef classes) | every request with DI | **−0.03 to −0.05 µs** | Removes pure-Python method-call overhead in the resolver pipeline. |
| `app/_exception_table.py::dispatch` (cdef class) | exception path only | **−0.02 µs** when hit | Walks `_handlers` dict; rare unless errors common. |
| `_extractors/*` mirrored as `.pyx` + `parameters.pyx` orchestrator rewrite | every parameterised request | **−0.05 to −0.10 µs** | Largest *and* riskiest — see §1.1. |

### 3.2 Medium impact (do if time)

| Module | Path | Best-case gain | Notes |
|---|---|---:|---|
| `_extractors/_missing.py` (`cdef inline`) | every missing-default path | −5 ns when hit | Inlining only. |
| `app/_asgi_entry.py` + `app/_http_dispatch.py` (`cdef class __call__`) | every request | −0.01 to −0.02 µs | Tiny coroutines; gain marginal. |
| `security/_bearer_parser.py` (`cdef inline` + `nogil`) | every auth-protected req | −5 to −10 ns when hit | Bearer-only path. |

### 3.3 Low / no impact (do not pursue in v1.2.9)

- All `openapi/` modules — cold path.
- All `cli/` modules — admin tooling.
- `core/lifecycle.py`, `core/websocket.py` — pre-compute is cold; per-connection
  setup is too rare to justify cdef.
- `middlewares/security_headers.py`, `middlewares/cors.py` — user-opt-in.
  Compile only if a user reports them as a bottleneck.
- `responses/_success.py` / `_error.py` / `_validation.py` — they call the
  response classes; gain is already captured by compiling the response classes.

---

## 4. Prioritized v1.2.9 sprint plan

Phases ordered so each phase **measures** before unlocking the next.

### Phase 1 — Response classes (low risk, certain gain)

- Create `responses/_json_response.pyx`, `_bytes_response.pyx`,
  `_internal_error.pyx`.  Mirror the existing `.py` API exactly.
- Add to `setup.py` `extensions`.
- Recompile + bench.
- Acceptance gate: FULL HANDLER ≤ 1.04 µs median across 5 runs.

### Phase 2 — DI resolver pipeline (medium risk, modest gain)

- Create `.pyx` siblings for `dependencies/_class_factory.py`,
  `_scope_cache.py`, `_override_lookup.py`, `_circular_detector.py`,
  `_resolver.py`.
- Leave `_callable_factory.py` and `_sig_cache.py` in pure Python
  (async ↔ cdef interaction is the riskiest territory, gain is small).
- Recompile + bench DI-heavy scenario.
- Acceptance gate: FULL HANDLER ≤ 1.01 µs in the DI scenario; no regression
  in non-DI scenarios.

### Phase 3 — Exception table (cheap, isolated)

- Create `app/_exception_table.pyx`.
- Recompile + run `tests/test_exception_handling.py` + bench.
- Acceptance gate: no regression in non-error paths.

### Phase 4 — Extractor cdef migration (highest risk)

This is the load-bearing decision (§1.1).  Sub-phases:

- **4a.** Create `.pyx` siblings for the **trivially-easy** extractors
  first: `_missing`, `header`, `cookie`, `path`, `query` (scalar).
  Add to `setup.py`.  Compile + bench.
- **4b.** Rewrite `parameters.pyx` to delegate to the cdef extractors
  built in 4a.  The orchestrator becomes a `cdef class
  ParameterPipeline` that holds the extractors as typed fields.
- **4c.** Migrate `body`, `body_limit`, `query_list`, `form`, `file`
  one at a time, re-measuring after each.
- Acceptance gate: each step must hold or improve the FULL HANDLER
  body-POST median; if any step regresses by >2%, fall back to Shape B
  for the remainder.

### Phase 5 — Bearer parser nogil (optional)

- `security/_bearer_parser.pyx` with `cdef inline` and `nogil` over
  `memchr`-style scanning.  Only invested in if Phase 1–4 land cleanly
  and there's time.

### Phase 6 — Fix the two known-failing tests (carry-over from v1.2.83)

- `tests/test_cli.py::TestNewCommand::test_new_creates_project_structure`
  — change expected dir to `my_api`.
- `example/tests/test_verification.py::test_start_enhanced_verification`
  — add `autouse` reset fixture in `example/tests/conftest.py`.

### Phase 7 — Add no-`.so` CI matrix step

- Run pytest once with `.so` files present, once with them deleted.
  Catches future drift between `.py` and `.pyx` implementations
  (the situation that produced the v1.2.811 bugs).

---

## 5. v1.2.9 target numbers

Anchor: v1.2.83 baseline = **1.07 µs FULL HANDLER median**, **~345k req/s total**
across the 8 benchmark scenarios, **5.50x vs FastAPI**.

| Scenario | v1.2.83 today | Conservative target (Phase 1 + 2 + 3 only) | Optimistic target (all 5 phases) |
|---|---:|---:|---:|
| FULL HANDLER cycle | 1.07 µs | **0.95 µs** | **0.85 µs** |
| process_parameters body POST | 0.80 µs | 0.75 µs | 0.65 µs |
| process_response dict payload | 0.72 µs | 0.65 µs | 0.58 µs |
| TachyonJSONResponse(dict) | 0.52 µs | 0.42 µs | 0.38 µs |
| Total throughput (8 scenarios) | ~345k req/s | ~385k req/s (+12%) | ~430k req/s (+25%) |
| Speedup vs FastAPI | 5.50x | **~6.1x** | **~7.0x** |

The conservative target assumes Phases 1+2+3 land with the expected ~10–15%
local wins.  The optimistic target assumes Phase 4 succeeds without
import-overhead regression.  We will only know which one we hit by Phase
4's measurement gates.

---

## 6. Risks and trade-offs

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Phase 4 `_extractors/*.pyx` introduces enough import overhead to wipe its per-extractor gain | Medium | Regression vs v1.2.83 | The sub-phase gates in §4 fail fast; if 4a + 4b don't show net gain, abandon Shape A and use Shape B for 4c. |
| cdef class inheriting from Starlette's `JSONResponse` hits ABI / MRO issues | Low | Phase 1 stalls | Cython documents this pattern; we already have a working `cdef class` over a Python parent in `processing/dispatch.pyx`. |
| `_callable_factory.py` async path is touched unintentionally and breaks | Low | DI regression | We explicitly defer `_callable_factory.pyx`; the resolver delegates to a pure-Python attribute. |
| Bench noise muddies the per-phase gate | Always | Wrong "go/no-go" call | Use 5-run medians (already standard in audit §6); set gate at "median ≤ X µs", not "any run ≤ X µs". |
| Compiled `parameters.pyx` rewrite ships before the rewrite is verified | Low | Production regression | The merge gate is "tests pass in both modes" (with `.so` and without).  Phase 7 (CI matrix) prevents this from coming back. |

---

## 7. What v1.2.9 looks like, concretely

One PR per Phase, in order:

| PR | Phase | Branch | Expected delta |
|---|---|---|---|
| #1 | 1 | `feature/v1.2.9-phase1-response-classes` | FULL HANDLER −0.04 to −0.07 µs |
| #2 | 2 | `feature/v1.2.9-phase2-di-resolver` | DI-scenario FULL HANDLER −0.03 to −0.05 µs |
| #3 | 3 | `feature/v1.2.9-phase3-exception-table` | exception path −0.02 µs |
| #4a | 4a | `feature/v1.2.9-phase4a-easy-extractors` | bench/measure only |
| #4b | 4b | `feature/v1.2.9-phase4b-parameters-rewrite` | body POST −0.05 to −0.10 µs |
| #4c | 4c | `feature/v1.2.9-phase4c-remaining-extractors` | body POST further −0.02 to −0.05 µs |
| #5 | 5 | `feature/v1.2.9-phase5-nogil-bearer` *(if time)* | auth-only path −5 to −10 ns |
| #6 | 6 | `fix/v1.2.9-known-failing-tests` | 367/367 |
| #7 | 7 | `ci/v1.2.9-no-so-matrix` | infra |

Each PR ends with a bench run pasted in the body and either an "advance"
or "fall back to Shape B" decision recorded.

---

## 8. Out of scope for v1.2.9

- Starlette 1.0 upgrade (v1.2.83 §3 risky bumps).
- pytest 9 / typer 0.25 upgrades.
- CI matrix across Python 3.10 / 3.11 / 3.12 (defer to v1.2.10 or v1.3).
- New features (none planned — v1.2.x is a perf + refactor line).

---

## 9. Closing the v1.2.8x phase

With this document v1.2.84 closes.  The v1.2.8x audit phase delivered:

- **v1.2.81** — example showcases every v1.2.x feature.
- **v1.2.82** — README + `docs/` brought up to v1.2.x state, including the
  new `16-cython-build.md`.
- **v1.2.83** — `audit-v1.2.83.md`: 76% coverage, 0 source TODOs, 1.07 µs
  baseline, 2 known-failing tests root-caused.
- **v1.2.84 (this)** — `cython-plan-v1.2.9.md`: 63 modules classified,
  ordered sprint plan, conservative + optimistic targets.

Ready to start **v1.2.9** with Phase 1.
