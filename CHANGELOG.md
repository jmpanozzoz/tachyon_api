# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

**Precompiled wheels: `pip install tachyon-api` now ships compiled Cython
extensions out of the box on the supported matrix.**

The `[fast]` extra used to require a manual `python setup.py build_ext
--inplace` step after install — quietly the biggest adoption barrier the
framework had.  This release introduces a `cibuildwheel`-based pipeline
that publishes prebuilt wheels for Linux (x86_64, aarch64), macOS
(x86_64, arm64), and Windows (x86_64) on CPython 3.10–3.13.  Users on a
matching platform get the 27 compiled `.so` modules automatically — no
build tools, no flags, no extra command.  Users on an unmatched platform
fall back to building from sdist (still works) or to the pure-Python
runtime fallback (also still works).

### Added

- `cibuildwheel` configuration in `pyproject.toml` covering CPython
  3.10–3.13 on Linux x86_64+aarch64, macOS x86_64+arm64, and Windows
  AMD64.  Skips PyPy, musllinux, free-threaded, and 32-bit targets.
- `.github/workflows/build-wheels.yml`: matrix wheel build on tag `v*`
  and `workflow_dispatch`, uploading wheels + sdist as run artifacts.
  No PyPI auto-publish — owner runs `twine upload` from the artifact.
  Both macOS architectures cross-compile from a single `macos-14`
  (Apple Silicon) runner; the `macos-13` Intel hosted pool stopped
  reliably allocating in May 2026 (jobs queued for hours), and Apple
  Silicon's SDK supports both targets natively.
- `setup.py` honors `TACHYON_SKIP_CYTHON=1` to force a pure-Python build
  even when Cython is importable.  Used by the CI fallback-verification
  job (`Tests (pure-Python fallback)`), which would otherwise compile
  `.so` files now that Cython is in `[build-system].requires`.

### Changed

- `pyproject.toml` `[tool.poetry.include]` now ships every `.pyx` and
  `.pxd` under `tachyon_api/` in the sdist (was 5 explicit entries; the
  build declares 27 extensions).  Sdist builds are now actually
  recompilable from source.
- `[build-system] requires` adds `setuptools>=61` and `cython>=3.0` so
  isolated PEP 517 builds (pip and cibuildwheel) have the toolchain
  available.  Poetry-core uses the project's existing `setup.py` rather
  than generating its own (the documented behavior when `setup.py` is
  present), so no `[tool.poetry.build]` script is needed.
- `.github/workflows/ci.yml` `Tests (pure-Python fallback)` job sets
  `TACHYON_SKIP_CYTHON=1` to preserve its "no `.so` files" invariant.
- README install section: `pip install tachyon-api` is documented as the
  one-step install on supported platforms.  The "manual `build_ext`
  required" caveat is gone; the `[fast]` extra is now only relevant for
  source builds on unsupported platforms.

---

## [1.2.993] — 2026-05-22

**Pre-v1.3.0 audit fixes: silent DI scope divergence in compiled mode + query
list DoS guard.**

A pre-v1.3.0 punch-list audit surfaced two real bugs that neither the test
suite nor the Phase 7 parity script could catch on their own.  This patch
release fixes both before tagging v1.3.0.

### Fixed

#### 1. `compiler.pyx` — `has_callable_deps` missed the DI scope check

`processing/compiler.pyx:115` flagged an endpoint as needing a per-request
`dependency_cache` ONLY when it had a `Depends(callable)` parameter — it
never checked whether class-typed dependencies were singleton-scoped vs
request-/transient-scoped.  `processing/compiler.py` did check.

Concretely, code like this:

```python
@injectable(scope=SCOPE_REQUEST)
class Counter: ...

@app.get("/x")
def handler(c: Counter): ...
```

would correctly create a fresh `Counter` per request under the pure-Python
fallback, but silently behave like a singleton when shipping the
Cython-compiled `.so` — because `has_callable_deps == False` meant the
orchestrator skipped allocating `dependency_cache`, so the class factory
fell through to the singleton path.

This is the same shape of bug as the v1.2.85 incident (security fix landed
in `.py` only).  The Phase 7 parity script cannot detect this class of
drift because the public API of both `CompiledEndpoint` is identical —
only the computed value differs.

**Fix**: `compiler.pyx:115` now mirrors `compiler.py:98–102` exactly,
including the `_scopes.get(annotation, SCOPE_SINGLETON) != SCOPE_SINGLETON`
clause for `KIND_DEP_CLASS` params.  Added
`tests/test_dependency_injection.py::test_request_scoped_class_di_creates_new_instance_per_request`
which fires three requests and asserts three distinct counter ids — fails
loudly if the divergence is ever reintroduced.

#### 2. `query_list` — unbounded CSV expansion was a DoS surface

`_extractors/query_list.py:27` (and the `.pyx` sibling) did
`values.extend(v.split(","))` with no cap on the final list size.  A
single request like `GET /items?ids=1,2,3,...,1000000` would happily
allocate a million-element Python list before hitting type conversion.

**Fix**: added `MAX_QUERY_LIST_SIZE = 1000` (importable from both `.py`
and `.pyx`).  When the extractor's running list exceeds it, returns
HTTP 422 with `"Query parameter '<name>' exceeds maximum list size (1000
items)"` and never grows further.  Added
`tests/test_query_params.py::test_query_list_under_cap_succeeds` and
`test_query_list_over_cap_rejected_with_422` — both exercise the limit
via real HTTP requests through the test client.

### Result

| | Before | After |
|---|---:|---:|
| Tests passing | 367/367 | **370/370** |
| Compiled-mode bugs found pre-v1.3.0 | 1 | **0** known |
| Parity script | ✓ | ✓ |

Both fixes ship in `.py` and `.pyx` simultaneously.  Compiled mode now
correctly allocates `dependency_cache` for non-singleton class DI, and
both modes reject query lists over 1000 items.

---

## [1.2.992] — 2026-05-22

**v1.2.9 Cython sprint — Phase 7/7 (CLOSER): CI matrix + `.py` ↔ `.pyx` parity check.**

Closes the sprint with the two pieces of infrastructure that prevent the
class of bug we lived through at v1.2.85: a security fix that shipped in
`parameters.py` but not in `parameters.pyx`, so compiled-mode users were
silently exposed.

Going forward every PR runs the test suite **in both modes** (pure-Python
and Cython-compiled), and a structural parity script blocks merges if a
`.py` exposes a public function/class/method that its `.pyx` sibling
doesn't (or vice-versa).  Logic divergence still requires the test suite —
the script only catches API drift — but API drift is what enabled the
v1.2.85 incident in the first place.

### Added

- `.github/workflows/ci.yml` — three CI jobs:
  - `parity` — runs `scripts/check_py_pyx_parity.py` (gate).
  - `test-pure-python` — installs without compilation, verifies no `.so`
    is present, runs `pytest tests/`.
  - `test-compiled` — installs Cython, compiles all extensions, verifies
    the critical `.so` artefacts exist, runs `pytest tests/`.
- `scripts/check_py_pyx_parity.py` — structural diff between `.py` and
  `.pyx` siblings:
  - Public top-level functions match.
  - Public top-level classes match.
  - For each shared class, public method set matches.
  - `_server_fast.pyx` is whitelisted as `.pyx`-only (low-level perf
    module without a Python equivalent).

### Fixed (caught by the new CI itself)

- `httptools` was a missing declared dependency.  `app/_fast_asgi_factory.py`
  top-level-imports `tachyon_api.server`, which imports
  `uvicorn.protocols.http.httptools_impl`.  Locally we always had
  `httptools` from some transitive install, so the gap went unnoticed.
  The clean Ubuntu CI runner blew up with `ModuleNotFoundError: httptools`
  on the very first run — exactly the kind of platform-divergence bug the
  no-`.so` job was added to catch.  Added `httptools >= 0.6.0` to
  `[tool.poetry.dependencies]`.

### Local result

```
$ python scripts/check_py_pyx_parity.py
✓ .py ↔ .pyx parity check passed (26 pair(s), 27 .pyx total)

$ pytest tests/
367 passed in ~25 s
```

### Sprint v1.2.9 — final summary

Closed in 7 phases between v1.2.91 and v1.2.992:

| Phase | Version | Delivered |
|---|---|---|
| 1 | 1.2.91 | Response classes as compiled `.pyx` |
| 2 | 1.2.92 | DI resolver pipeline as cdef classes |
| 3 | 1.2.93 | `ExceptionTable` as cdef class |
| 4a | 1.2.94 | Easy extractors as cdef class (used by pure-Python fallback) |
| 4b.1 | 1.2.95 | F11 fast-int / fast-float migrated into query/path extractors |
| 4b.2 | 1.2.96 | `parameters.pyx` rewritten to delegate to cdef extractors |
| 4b.3 | 1.2.97 | `.pxd` + `cimport` — typed cdef-class slot dispatch |
| 4c | 1.2.98 | Remaining four extractors as cdef; `parameters.pyx` = pure orchestrator |
| 5 | 1.2.99 | `parse_bearer_header` compiled (1.61× on the call) |
| 6 | 1.2.991 | Fix stale CLI test (suite back to 367/367) |
| 7 | 1.2.992 | CI matrix + parity check |

Hot-path measurements (10-run median, compiled mode):

| | v1.2.83 baseline | v1.2.992 (sprint close) | Δ |
|---|---:|---:|---:|
| FULL HANDLER cycle | 1.05 µs | **0.94 µs** | **−10.5%** |
| `process_parameters` — path+query | 0.57 µs | 0.58 µs | +1.8% |
| `process_parameters` — body POST | — | 0.77 µs | — |
| `process_parameters` — no params | 0.16 µs | 0.16 µs | unchanged |
| `parse_bearer_header` per call | 0.268 µs | **0.166 µs** | **1.61×** |
| Tests | 366/367 | **367/367** | clean |
| Compiled modules | 7 | **27** | +20 |
| `parameters.pyx` LOC | 460 (monolith) | **175 (orchestrator)** | −62% |

The conservative target of ≤ 0.95 µs FULL HANDLER median is met.  More
importantly, the SRP refactor (eight atomic extractors in their own
`.pyx`/`.pxd` pairs) is now visible in production compiled mode, not just
in the pure-Python fallback.

---

## [1.2.991] — 2026-05-22

**v1.2.9 Cython sprint — Phase 6/7: fix stale CLI test (suite now 367/367).**

`test_new_creates_project_structure` had been red since the v1.2.81 sprint
that added `validate_name` (hyphen → underscore normalisation, Python-keyword
rejection).  The test still asserted on `Path(tmpdir) / "my-api"` while
the CLI now creates `Path(tmpdir) / "my_api"` and prints a normalisation
notice — the production code is correct, the test was outdated.

### Fixed

- `tests/test_cli.py::TestNewCommand::test_new_creates_project_structure`:
  asserts the project lives at the normalised name (`my_api`) and that the
  stdout shows both the input (`my-api`) and the normalised form
  (`my_api`).

### Result

| | Before | After |
|---|---:|---:|
| Tests passing | 366/367 | **367/367** |
| Tests failing | 1 | **0** |

No production code changed in this phase — Phase 6 is purely a test fix.

---

## [1.2.99] — 2026-05-22

**v1.2.9 Cython sprint — Phase 5/7: Bearer header parser compiled.**

`parse_bearer_header` is called by `HTTPBearer` and `OAuth2PasswordBearer`
on every authenticated request — lukewarm path.  Compiling it to a cdef
module yields a clean 1.6× speedup on the parser call itself, saving
~100 ns per authenticated request.

The v1.2.9 plan tagged Phase 5 as `nogil` + `memchr` (optional).  Hand-
rolled whitespace scanning would diverge from `str.split()` on
multi-whitespace / non-space whitespace inputs, so this commit ships the
compile-only version.  A strict RFC 7235 token parser with `memchr` +
`nogil` is left for v1.3.x.

### Added

- `security/_bearer_parser.pyx` — `cpdef parse_bearer_header` with typed
  locals (`cdef list parts`, `cdef str scheme`).

### Changed

- `setup.py`: one new `Extension` (`tachyon_api.security._bearer_parser`).
  Total compiled modules: 27.

### Measurements

`parse_bearer_header('Bearer <jwt-like-string>')` × 1 M iterations:

| Variant | µs/call | call/s | Δ |
|---|---:|---:|---:|
| Pure-Python `.py` | 0.268 | 3.7 M | (baseline) |
| Compiled `.pyx` | **0.166** | **6.0 M** | **1.61×** |

FULL HANDLER cycle: 5-run median 0.95 µs — same band as Phase 4c, no
regression (bearer is not on the FULL HANDLER bench path).

### Verification

- 366/367 tests pass with `.so` loaded.
- 366/367 tests pass without `.so`.
- Edge cases verified equivalent to pure-Python version: empty / None
  input, single-part input, scheme ≠ "bearer", multi-whitespace
  separators, tab separator, surrounding whitespace, 3-part input.

---

## [1.2.98] — 2026-05-22

**v1.2.9 Cython sprint — Phase 4c/7: remaining four extractors migrated to
cdef classes; `parameters.pyx` is now pure orchestrator.**

The orchestrator inlined `_process_body`, `_process_form`, `_process_file`,
and `_process_query_list` until this phase.  Phase 4c moves all four into
their own compiled cdef-class extractors (sibling to header/cookie/query/path
from Phase 4b), plus the `BodySizeChecker` helper used by body — and deletes
the inline methods from `parameters.pyx` entirely.

### Added

- `processing/_extractors/body.pyx` + `.pxd` — `cdef class BodyExtractor`
  with `async def extract`; size checking delegates to a `cimport`-ed
  `BodySizeChecker`.
- `processing/_extractors/body_limit.pyx` + `.pxd` — `cdef class
  BodySizeChecker` with `cpdef check_content_length` /
  `cpdef check_body_length` and a `cdef inline _too_large_response` helper.
- `processing/_extractors/form.pyx` + `.pxd` — `cdef class FormExtractor`
  with `cpdef extract`.
- `processing/_extractors/file.pyx` + `.pxd` — `cdef class FileExtractor`
  with `cpdef extract`.
- `processing/_extractors/query_list.pyx` + `.pxd` — `cdef class
  QueryListExtractor` with `cpdef extract`; handles both repeated keys and
  CSV form, then delegates to `TypeConverter.convert_list_values_bare`.

### Changed

- `processing/parameters.pyx`:
  - Deleted four inline helper methods (`_process_body`, `_process_form`,
    `_process_file`, `_process_query_list`).
  - Added `cimport` + Python alias import for the four new extractors.
  - `ParameterProcessor` now holds **eight** typed cdef-class extractors as
    fields, instantiated once in `__init__` (body extractor receives
    `max_body_size` at construction, matching the pure-Python
    `parameters.py` semantics).
  - The orchestrator loop is now a straight dispatch: read `kind`, call
    the matching extractor, unpack `(value, error)`.
- `setup.py`: five new `Extension` entries (body, body_limit, form, file,
  query_list).  Total compiled modules: 26.

### Measurements (10-run median, compiled mode)

| Metric | Phase 4b.3 | Phase 4c | Δ vs 4b.3 | Δ vs v1.2.83 baseline |
|---|---:|---:|---:|---:|
| **FULL HANDLER cycle** | 0.95 µs | **0.94 µs** | −1.1% | **−10.5%** |
| `process_parameters` — path+query | 0.595 µs | **0.58 µs** | −2.5% | +1.8% |
| `process_parameters` — body POST | — | 0.77 µs | — | — |
| `process_parameters` — no params | 0.16 µs | 0.16 µs | unchanged | unchanged |

path+query is now within 1.8% of the pre-SRP baseline (0.57 µs).  The
architectural win is bigger than the per-metric delta: `parameters.pyx`
went from a ~265-line monolith with four inline `_process_*` methods to a
~175-line pure dispatch loop.

### Verification

- 366/367 framework tests pass with `.so` loaded.
- 366/367 tests pass without `.so` (pure-Python fallback).
- 1 known-failing CLI test (`test_new_creates_project_structure`) is
  pre-existing — tracked for Phase 6.
- Body-size limit semantics preserved (v1.2.85 hardening: 2 MB default;
  `Tachyon(max_body_size=...)` override).
- F11 fast-int/fast-float preserved end-to-end.

### Sprint status

After Phase 4c, the v1.2.9 sprint sits at **0.94 µs FULL HANDLER median**
(−10.5% vs v1.2.83 baseline) with full SRP in compiled mode.  Remaining
phases: F5 (nogil bearer parser, optional), F6 (fix the known-failing
test), F7 (no-`.so` CI matrix + parity check).

---

## [1.2.97] — 2026-05-22

**v1.2.9 Cython sprint — Phase 4b.3/7: `.pxd` declarations + `cimport` recover
the Phase 4b.2 path+query regression.**

Phase 4b.2 introduced cross-module cdef dispatch overhead because
`parameters.pyx` held extractor instances as `cdef object` (untyped) — each
call went through Python's method machinery.  This phase adds `.pxd`
declarations to each cdef extractor and uses `cimport` to get typed C-level
references, enabling direct extension-type slot dispatch.

### Added (4 new `.pxd` files)

- `processing/_extractors/header.pxd` — `cdef class HeaderExtractor` + `cpdef extract`
- `processing/_extractors/cookie.pxd` — same for `CookieExtractor`
- `processing/_extractors/query.pxd` — same for `QueryExtractor`
- `processing/_extractors/path.pxd` — same for `PathExtractor`

### Changed

- Each extractor's `.pyx`: `def extract(...)` → `cpdef extract(self, object descriptor, object source)`
  (`cpdef` required to match the `.pxd` declaration).
- `processing/parameters.pyx`:
  - `cimport` each extractor class for the C-level type.
  - Renamed Python imports to `_X_py` aliases for use as constructors.
  - Extractor fields typed as the actual cdef class (`cdef HeaderExtractor _header_extractor`) instead of `cdef object`.
  - Cython now generates direct slot dispatch for `self._header_extractor.extract(...)`.

### Measurements (10-run median, compiled mode)

| Metric | Phase 4b.2 | Phase 4b.3 | Δ vs 4b.2 | Δ vs v1.2.83 baseline |
|---|---:|---:|---:|---:|
| **FULL HANDLER cycle** | 0.965 µs | **0.95 µs** | −1.5% | **−9.5%** |
| `process_parameters` — path+query | 0.635 µs | **0.595 µs** | **−6.3%** | +4.4% |
| `process_parameters` — body POST | 0.80 µs | 0.80 µs | unchanged | unchanged |
| `process_parameters` — no params | 0.16 µs | 0.16 µs | unchanged | unchanged |

path+query regression dropped from +11.4% (4b.2) to +4.4% (4b.3) vs the
v1.2.83 baseline.  Remaining gap is `descriptor.*` Python attribute access
inside the extractors — not addressable without deeper changes.

### Verification

- 366/367 framework tests pass with `.so` loaded.
- 366/367 framework tests pass without `.so` (pure-Python fallback) — both
  modes agree.  `.pxd` is a Cython-only artifact, no impact on `.py`.
- F11 fast-int/fast-float preserved.

### Sprint status

After Phase 4b.3 the v1.2.9 sprint hits **0.95 µs FULL HANDLER median**,
matching the conservative target (`≤ 0.95 µs`) declared in `docs/cython-plan-v1.2.9.md`.

Remaining: Phase 4c (body/form/file/query_list to cdef), Phase 5 (nogil
bearer), Phase 6 (fix known-failing tests), Phase 7 (CI matrix).

---

## [1.2.96] — 2026-05-22

**v1.2.9 Cython sprint — Phase 4b.2/7: `parameters.pyx` delegates to cdef
extractors (Shape A active).**  The load-bearing pivot of the sprint.  In
compiled mode, the 5 cdef extractors built in Phase 4a are no longer dead
code — `parameters.cpython-*.so` now imports and uses them.

**Honest measurement:** FULL HANDLER gate passes within margin (+1.6%);
path+query micro-bench has a +11% regression from cross-module cdef dispatch
overhead.  A `.pxd`-based fix is documented as a follow-up.

### Changed

- **`processing/parameters.pyx`** — `ParameterProcessor` now holds the four
  migrated cdef extractor instances as `cdef object` fields (header, cookie,
  query, path), instantiated once in `__init__`.  Each `_KIND_*` branch in
  `process_parameters` delegates instead of running inline logic.

  Still inlined (Phase 4c targets): `_process_body`, `_process_form`,
  `_process_file`, `_process_query_list`.

  Removed: the `_fast_int` / `_fast_float` cdef helpers — they now live in
  `query.pyx` / `path.pyx` (Phase 4b.1).

  `_DEFAULT_MAX_BODY_SIZE` stays at `2 * 1024 * 1024` (v1.2.85 fix preserved).

### Changed (extractors — drop NamedTuple)

All extractors (`.py` and `.pyx`) now return a **plain 2-tuple `(value, error)`**
instead of an `ExtractorResult` NamedTuple.  Discovery: an initial Shape A
implementation with NamedTuple regressed `path+query` from 0.57 µs → 0.90 µs
(+58%).  Plain tuples halved the overhead.

Updated extractors: `_missing` · `header` · `cookie` · `query` · `path` (both
`.py` and `.pyx`) · `body` · `form` · `file` · `query_list` (`.py` only).

Updated orchestrators: `processing/parameters.py` and `processing/parameters.pyx`
use tuple unpacking `val, err = self._x.extract(...)` instead of attribute
access.

`ExtractorResult` NamedTuple in `_base.py` retained as a documentation artifact
(no longer constructed at runtime).

### Measurements

**`benchmark/profile_hotpath.py` (10-run median, compiled mode):**

| Metric | v1.2.83 baseline | v1.2.95 (Phase 4b.1) | v1.2.96 | Δ vs 4b.1 |
|---|---:|---:|---:|---:|
| **FULL HANDLER cycle** | 1.07 µs | 0.94 µs | **0.965 µs** | +1.6% |
| `process_parameters` — path+query | 0.57 µs | 0.57 µs | **0.635 µs** | **+11.4%** |
| `process_parameters` — no params | 0.16 µs | 0.16 µs | 0.16 µs | unchanged |
| `process_parameters` — body POST | 0.80 µs | 0.80 µs | 0.80 µs | unchanged |

**Phase 4b.2 gate (FULL HANDLER ≤ 0.97 µs median): PASSED with 0.005 µs of margin.**

### The path+query regression — analysis

The 11% regression on `path+query` is the **cost of cross-module cdef class
dispatch**.  When `parameters.pyx` calls `self._path_extractor.extract(...)`,
Cython treats `self._path_extractor` as `cdef object` (untyped reference) —
the call goes through Python's method dispatch (~30–60 ns) instead of a
direct cdef class slot call.  With 2 typed params per request that's ~60–120 ns
of added overhead, which matches the measured 0.06 µs regression.

**What recovers this**: a `.pxd` declaration file for each extractor + `cimport`
in `parameters.pyx`.  Deferred to a follow-up if the regression matters in
real-world endpoints (the FULL HANDLER gate passing suggests it's swallowed
by the rest of the request cycle).

### Verification

- 366/367 framework tests pass with `.so` loaded.
- 366/367 framework tests pass without `.so` (pure-Python fallback) — both
  modes agree.
- `_extractors/*.cpython-*.so` are no longer dead code in compiled mode.
- F11 fast-int/fast-float (PR #54) preserved end-to-end.

### Architectural impact

This is the first phase that makes the v1.2.x SRP refactor **visible in
production**.  Before this, compiled users got the monolithic
`parameters.so` and the SRP layout only existed in `.py` fallback.  After
this, both modes use the same modular layout — preventing future `.py`/`.pyx`
divergences of the kind v1.2.85 had to fix.

### Phase 4c preview

Remaining inlined extractors: `body`, `form`, `file`, `query_list`.  These
are lower-traffic paths.  Phase 4c moves them to compiled `.pyx` and updates
the orchestrator to delegate.

---

## [1.2.95] — 2026-05-22

**v1.2.9 Cython sprint — Phase 4b.1/7: migrate F11 fast-int/fast-float into the
cdef extractors.**  Prerequisite for Phase 4b.2 (parameters.pyx rewrite).

### Why this phase exists

Phase 4a compiled five extractors as `cdef class` siblings of the `.py`
versions.  But the current `parameters.pyx` still has C-level
`_fast_int` / `_fast_float` (F11 from v1.1.x) using `strtol` / `strtod`
inline in its `_process_query` / `_process_path`.  If Phase 4b.2
naively delegates to the new extractors, those F11 fast paths disappear
in compiled mode — a real regression for int/float path and query params.

This phase **moves F11 into the cdef extractors themselves** so Phase 4b.2
can delegate without losing the optimization.

### Changed (extractors only)

- **`processing/_extractors/query.pyx`** — added `cdef _fast_int(str s)`
  and `cdef _fast_float(str s)` using `libc.stdlib.strtol` / `strtod` and
  `cpython.unicode.PyUnicode_AsUTF8AndSize`.  `QueryExtractor.extract`
  uses them when `descriptor.base_type is int` / `is float`, otherwise
  falls back to `TypeConverter.convert_value_bare`.  On conversion
  failure: returns a 422 `validation_error_response`.

- **`processing/_extractors/path.pyx`** — added `cdef _fast_int_path` and
  `cdef _fast_float_path` (same shape as above but conversion failure
  returns 404 `{"detail": "Not Found"}`, matching the original
  `parameters.pyx` semantics for path-param type mismatch).

The `cdef` helpers are file-local — intra-module zero-overhead calls.
Code duplication between `query.pyx` and `path.pyx` is intentional: the
return values on failure differ (422 vs 404) so a shared helper would
need an extra branch, which costs more than the duplicated ~15 lines.

### Measurements (compiled `.pyx` only)

| Extractor scenario | Phase 4a baseline | Phase 4b.1 | Δ |
|---|---:|---:|---:|
| `PathExtractor.extract` — string hit | 0.349 µs | 0.350 µs | unchanged (str path doesn't use F11) |
| **`PathExtractor.extract` — int conversion** | 0.407 µs | **0.239 µs** | **−41%** |
| `QueryExtractor.extract` — string hit | 0.332 µs | 0.334 µs | unchanged |
| **`QueryExtractor.extract` — int conversion** | (~0.40 µs est.) | **0.252 µs** | **~−37%** |

F11 brings the int/float fast path back; string path is unchanged (as it
should be — `TypeConverter` was already a no-op for `str`).

### FULL HANDLER

| Metric | Phase 4a baseline | Phase 4b.1 | Δ |
|---|---:|---:|---:|
| FULL HANDLER cycle (10-run median) | 0.95 µs | 0.94 µs | within noise |

FULL HANDLER is unchanged because `parameters.cpython-*.so` still doesn't
use the new extractors — Phase 4b.2 is where it starts to matter.

### Verification

- 366/367 framework tests pass with compiled `.so` loaded.
- Pure-Python users with the new `.py` extractors still take the
  `TypeConverter` path (the F11 helpers are Cython-only — they live in
  `.pyx`, not `.py`).  No `.py` divergence introduced.

### Next: Phase 4b.2

Rewrite `parameters.pyx` to:
1. Hold the cdef extractor instances as typed fields on `ParameterProcessor`.
2. Delegate each `_KIND_*` branch to `self._<kind>_extractor.extract(p, source)`.
3. Drop the inline `_fast_int` / `_fast_float` (now lives in the extractors).

Measurement gate: FULL HANDLER ≤ 0.97 µs median (= ≤ +2% vs Phase 4a's 0.95).
If it regresses, fall back to Shape B.

---

## [1.2.94] — 2026-05-22

**v1.2.9 Cython sprint — Phase 4a/7: easy extractors compiled (cdef class).**
Five trivially-easy extractors get `.pyx` siblings.  **Important caveat:**
in compiled mode, `parameters.cpython-*.so` still contains the inline
v1.2.0 logic and doesn't import these — they're dead code in compiled mode
until Phase 4b rewrites the orchestrator.  Pure-Python fallback users get
the speedup today.

### Added (5 new compiled modules)

- **`processing/_extractors/_missing.pyx`** — default-vs-error helper.
- **`processing/_extractors/header.pyx`** — `cdef class HeaderExtractor`.
- **`processing/_extractors/cookie.pyx`** — `cdef class CookieExtractor`.
- **`processing/_extractors/query.pyx`** — `cdef class QueryExtractor` (scalar).
- **`processing/_extractors/path.pyx`** — `cdef class PathExtractor`
  (incl. null-byte rejection).

Deferred to Phase 4c: `body`, `body_limit`, `query_list`, `form`, `file`.

### Changed

- **`setup.py`** — five new `Extension` entries.  Total `.so` count: 16 → 21.

### Added (benchmark)

- **`benchmark/profile_extractors.py`** — direct micro-bench of the 5 easy extractors.

### Measurements

**`benchmark/profile_extractors.py`, compiled vs pure-Python fallback:**

| Extractor | Pure Python `.py` | Compiled `.pyx` | Δ |
|---|---:|---:|---:|
| `HeaderExtractor.extract` — hit | 0.319 µs | 0.334 µs | +5% (noise — operation too short) |
| `CookieExtractor.extract` — hit | 0.314 µs | **0.260 µs** | **−17%** |
| `QueryExtractor.extract` — string hit | 0.414 µs | **0.332 µs** | **−20%** |
| `PathExtractor.extract` — string hit | 0.452 µs | **0.349 µs** | **−23%** |
| `PathExtractor.extract` — int conversion | 0.504 µs | **0.407 µs** | **−19%** |

Average: ~15% gain across the 5.  Pure-Python fallback users get this
directly; compiled-mode users will benefit once Phase 4b lands.

**`benchmark/profile_hotpath.py` (FULL HANDLER, 10-run median):**

| Metric | v1.2.93 baseline | v1.2.94 | Δ |
|---|---:|---:|---:|
| FULL HANDLER cycle | 0.94 µs | 0.95 µs | within noise |

Phase 4a gate ("compile + measure only, no FULL HANDLER regression") **PASSED**.

### Verification

- 366/367 framework tests pass with compiled `.so` loaded.
- Compiled extractors load from `.so` (verified via `__file__`).
- `isinstance(HeaderExtractor(), HeaderExtractor)` works — cdef class is a proper Python type.

### Phase 4b preview

Phase 4b will rewrite `parameters.pyx`'s body to import these cdef
extractors and delegate to them instead of inlining the extraction logic.
This is the load-bearing decision flagged in `docs/cython-plan-v1.2.9.md`
(Shape A vs Shape B).  Phase 4b will measure FULL HANDLER on a
param-heavy endpoint with the rewritten `parameters.pyx`; if the
cross-module cdef-class call overhead wipes the gain, the plan falls
back to Shape B (inline cdef classes inside a single `parameters.pyx`).

---

## [1.2.93] — 2026-05-22

**v1.2.9 Cython sprint — Phase 3/7: ExceptionTable compiled (cdef class).**
Result is honestly modest: a wash on the per-dispatch micro-bench (the
exception path is dominated by `JSONResponse` construction, which is pure
Starlette and not compiled).  Ships anyway for consistency with Phases 1+2,
zero regression in the non-error hot path, and to set up the cdef-class
posture for future improvements.

### Added

- **`tachyon_api/app/_exception_table.pyx`** — `cdef class ExceptionTable`.
  Same public surface as the `.py` sibling: `register()`, `dispatch()`,
  `_invoke()`, `_http_exception_response()`.
- **`benchmark/profile_exc.py`** — exception-path micro-bench (was missing).

### Changed

- **`setup.py`** — one new `Extension`.  Total compiled `.so` count: 15 → 16.

### Measurements

**`benchmark/profile_exc.py`, compiled vs pure-Python fallback:**

| Dispatch path | Pure Python `.py` | Compiled `.pyx` | Δ |
|---|---:|---:|---:|
| handler match (HTTPException subclass) | 3.798 µs/iter | 3.854 µs/iter | +1.5% (noise) |
| no match — default body | 3.014 µs/iter | **2.888 µs/iter** | **−4.2%** |

The "no match" path improves measurably (one less callable invocation,
just a dict walk + JSONResponse construct).  The "match" path is dominated
by the user-handler call + `JSONResponse({"code": ...})` construction;
the cdef-class dispatch overhead is ≤ 5% of the cycle and disappears in
noise.

**`benchmark/profile_hotpath.py` (10-run median, no-error path):**

| Metric | v1.2.92 baseline | v1.2.93 | Δ |
|---|---:|---:|---:|
| FULL HANDLER cycle | 0.93 µs | 0.94 µs | within noise |

Phase 3 gate ("no regression in non-error paths") **PASSED**.

### Verification

- `tests/test_exception_handling.py` + `tests/test_v1_2_811_fixes.py`: 17/17 pass.
- Full framework suite: 366/367 (only the pre-existing CLI test).

### Why ship a wash?

Two reasons:

1. **Plan consistency** — Phases 1+2 set the precedent of "compile everything
   in the SRP layout for v1.2.9".  Skipping Phase 3 leaves `_exception_table.py`
   as the only DI/app/`hot path module without a `.pyx` sibling.
2. **Infrastructure for later** — Phase 7 (no-`.so` CI matrix step) will
   check that every compiled module's behavior matches its `.py` sibling.
   Phase 3 keeps `ExceptionTable` in scope for that check.

The CHANGELOG entry is honest about the measured cost; future readers
considering similar marginal compiles can use this as the baseline.

---

## [1.2.92] — 2026-05-22

**v1.2.9 Cython sprint — Phase 2/7: DI resolver pipeline compiled (cdef class).**
Result: **resolve_dependency 41–50% faster** across all three scopes; FULL
HANDLER unchanged in non-DI scenarios (as expected — the resolver isn't on
the path for endpoints without `@injectable` or `Depends`).

### Added (5 new compiled modules)

- **`processing/dependencies/_override_lookup.pyx`** — `cdef class OverrideLookup`
- **`processing/dependencies/_scope_cache.pyx`** — `cdef class ScopeCache`
- **`processing/dependencies/_circular_detector.pyx`** — `cdef class CircularDetector`
- **`processing/dependencies/_class_factory.pyx`** — `cdef class ClassFactory`
- **`processing/dependencies/_resolver.pyx`** — `cdef class DependencyResolver`
  (orchestrator; preserves the `_resolving` legacy attribute for backward compat)

Unlike Phase 1, these classes have no Python parent class, so `cdef class`
is viable and the typed attribute slots (`cdef object _app`, etc.) actually
take effect.

`_callable_factory.py` and `_sig_cache.py` deliberately stay in pure Python
per the v1.2.84 plan: callable factory mixes async + recursion + nested
resolve and is the riskiest cdef target; sig cache is a dict lookup
already at C level.

### Changed

- **`setup.py`** — five new `Extension` entries.  Cython now produces 15
  compiled `.so` files (was 10 after Phase 1).

### Added (benchmark)

- **`benchmark/profile_di.py`** — DI-specific micro-bench measuring
  `resolve_dependency` for each scope.  Was missing from the bench suite;
  needed to validate Phase 2.

### Measurements

**`benchmark/profile_di.py`, compiled vs pure-Python fallback:**

| Scope | Pure Python `.py` | Compiled `.pyx` | Δ |
|---|---:|---:|---:|
| singleton (cache hit) | 0.343 µs/iter | **0.172 µs/iter** | **−50%** |
| request (fresh cache) | 0.970 µs/iter | **0.557 µs/iter** | **−43%** |
| transient (always new) | 0.889 µs/iter | **0.522 µs/iter** | **−41%** |

Per request, assuming 1–2 deps resolved, that's roughly **−0.20 to −0.40 µs
on endpoints with DI**.

**`benchmark/profile_hotpath.py` (no-DI scenarios, 10-run median):**

| Metric | v1.2.91 baseline | v1.2.92 | Δ |
|---|---:|---:|---:|
| FULL HANDLER cycle | 0.93 µs | 0.93–0.94 µs | within noise |

Phase 2 gate ("no regression in non-DI") **PASSED**.

### Verification

- 366/367 framework tests pass with compiled `.so` loaded.
- The `DependencyResolver._resolving` legacy attribute (used by at least one
  test) is preserved as a `cdef public set` mirroring `_circular._resolving`.
- The orchestrator's `__init__` ordering is unchanged: collaborators are
  constructed in the same sequence, `OverrideLookup` reads
  `app.dependency_overrides` lazily at lookup time (preserves the
  pre-construction tolerance from v1.2.4).

### v1.2.9 status

After Phase 2: FULL HANDLER stable at ~0.93 µs (no-DI); DI scenarios get
visible per-request speedups proportional to how many deps the endpoint uses.

Phases remaining: 3 (ExceptionTable), 4a/b/c (extractors), 5 (nogil bearer),
6 (fix 2 known-failing tests), 7 (no-`.so` CI matrix).

---

## [1.2.91] — 2026-05-22

**v1.2.9 Cython sprint — Phase 1/7: response classes compiled.**
First phase of the Cython sprint defined in `docs/cython-plan-v1.2.9.md`.
**Result exceeds the conservative projection by ~2×:** FULL HANDLER cycle
drops from 1.05 µs → **0.93 µs median (−11%)**, well below the gate of 1.04 µs.

### Added

- **`tachyon_api/responses/_json_response.pyx`** — Cython sibling of the
  `.py` file. Same class layout (regular `class` inheriting from Starlette's
  `JSONResponse` for `isinstance` compatibility), but typed locals
  (`cdef Py_ssize_t n`, `cdef list headers`) and Cython byte-code
  compilation of the methods.
- **`tachyon_api/responses/_bytes_response.pyx`** — same pattern for
  pre-encoded bytes.
- **`tachyon_api/responses/_internal_error.pyx`** — same pattern for the
  500 singleton.

### Changed

- **`setup.py`** — three new `Extension` entries for the response `.pyx`
  modules.  Cython now produces 10 compiled `.so` files (was 7).

### Planning correction

The v1.2.84 plan asserted "cdef class on top of a Python parent is fully
supported by Cython".  **This was wrong.**  Cython's `cdef class` requires
the parent to be another extension type (or `object`).  Starlette's
`JSONResponse` is a regular Python class, so `cdef class
TachyonJSONResponse(JSONResponse)` fails to compile with
`First base of 'TachyonJSONResponse' is not an extension type`.

**Workaround applied:** compile the module as Cython (`.pyx`) but keep the
class as a regular Python `class` (no `cdef class`).  The gain comes from:
- typed C locals inside `__init__` (`Py_ssize_t n`, `list headers`),
- byte-code compilation of `__call__` and `__init__`,
- module-level `cdef` constants resolved at compile time.

**Empirically the gain is larger than the original cdef-class projection
predicted:** the plan estimated −0.04 to −0.07 µs FULL HANDLER; we measured
−0.12 µs median across 5 runs.  Reason: the response classes are
constructed *very* frequently and the methods are tiny — Cython's bytecode
optimizations on small methods can outperform the cdef-class slot win for
this specific shape.

The plan is updated implicitly: Phase 2 (DI resolver) and Phase 3
(ExceptionTable) face the same inheritance constraint and will use the
same approach.  Targets remain reachable.

### Measurements (5-run medians, compiled mode)

| Metric | v1.2.85 baseline | v1.2.91 | Δ |
|---|---:|---:|---:|
| **FULL HANDLER cycle** | 1.05 µs | **0.93 µs** | **−11.4%** |
| TachyonJSONResponse(dict) | 0.52 µs | **0.40 µs** | **−23.1%** |
| process_response — dict payload | 0.72 µs | **0.61 µs** | **−15.3%** |
| process_parameters body POST | 0.80 µs | 0.80 µs | 0 (Phase 4 territory) |

Perf gate (FULL HANDLER ≤ 1.04 µs median): **passed** with 0.11 µs of headroom.

### Verification

- 366/367 framework tests pass with compiled `.so` loaded.
- 16/17 example tests pass.
- `isinstance(response, JSONResponse)` returns True for the compiled classes (verified explicitly).

### What this unlocks

The v1.2.9 conservative target (FULL HANDLER 0.95 µs) is **already met**
after Phase 1 alone.  Phases 2 and 3 should push toward the optimistic
target of 0.85 µs; Phase 4 (extractor migration) decides whether we land
there or somewhere between.

---

## [1.2.85] — 2026-05-22

**Fix the `parameters.pyx` ↔ `parameters.py` security divergence.**
Two v1.2.0 audit fixes were applied to `parameters.py` but never propagated
to `parameters.pyx` — production users running compiled Cython
(`pip install tachyon-api[fast]`) silently retained the pre-v1.2.0 unsafe
behavior.  Discovered while preparing the v1.2.9 sprint plan (v1.2.84) and
fixed before starting Phase 1.

### Security fixes (compiled-Cython users only)

- **`_DEFAULT_MAX_BODY_SIZE`** in `parameters.pyx`: `10 * 1024 * 1024` → `2 * 1024 * 1024`
  (10 MB → 2 MB).  Matches `parameters.py` set in v1.2.0 audit (PR #28).
  Compiled-mode users had 5× the body-size limit of pure-Python-mode users.
- **Null-byte rejection** in `_process_path` of `parameters.pyx`: added
  `if "\x00" in value_str: return None, validation_error_response(...)`
  before any type conversion.  Matches `parameters.py` set in v1.2.0
  security audit (PR #27 — path-traversal hardening).  Compiled-mode users
  could submit `\x00` in path params and reach the application handler.

Cython recompiled (`python setup.py build_ext --inplace`).

### Why v1.2.83 audit missed this

The audit measured each implementation in isolation; it did not diff `.py`
vs `.pyx` line-by-line.  The diff would have surfaced both at once.
**Action for v1.2.9 Phase 7**: the no-`.so` CI matrix step gains a
complementary check — run the security-audit tests in both modes; if
behavior diverges, fail the matrix.

### Verification

- 366/367 framework tests pass (with `.so` loaded).
- Compiled-mode smoke:
  - `GET /p/foo%00bar` → 422 `{"code": "VALIDATION_ERROR", "error": "Invalid path parameter: x"}` (was: routed to handler with embedded null byte).
  - `Tachyon(max_body_size=...)` still accepted; default lowered as expected.
- FULL HANDLER cycle 1.04 – 1.06 µs across 3 runs — within v1.2.84 noise
  (the extra `"\x00" in str` check is sub-nanosecond).

---

## [1.2.84] — 2026-05-22

**v1.2.8x project audit / Cython prep — sub-version 4/4: Cython impact analysis.**
Closes the v1.2.8x phase.  Produces `docs/cython-plan-v1.2.9.md`: the
prioritized, quantified plan for the v1.2.9 sprint, built on the v1.2.83
audit baseline.

### Added

- **`docs/cython-plan-v1.2.9.md`** — 9-section plan with:
  1. **State of compilation today** — 7 `.pyx` modules currently compiled.
  2. **The `parameters.pyx` divergence** — load-bearing finding: v1.2.2 split
     `parameters.py` into 10 `_extractors/*.py` modules but `parameters.pyx`
     still ships the pre-v1.2.2 monolithic logic.  In compiled mode the new
     extractors are dead code.  Two shapes documented for v1.2.9 (mirror
     SRP in Cython vs. embed in monolithic `.pyx`); recommended approach is
     "Shape A in stages, with a perf gate".
  3. **Classification of all 63 modules** — hot/lukewarm/cold × cdef
     feasibility (Easy/Medium/Hard/N/A) for every module under `tachyon_api/`.
  4. **Per-module impact estimates** — highest expected impact: response
     classes (−0.04 to −0.07 µs), DI resolver pipeline (−0.03 to −0.05 µs),
     extractor mirroring + parameters.pyx rewrite (−0.05 to −0.10 µs).
  5. **Prioritized 7-phase sprint plan** — Phase 1 response classes →
     Phase 2 DI resolver → Phase 3 exception table → Phase 4 extractor
     migration (sub-phased with per-step perf gates) → Phase 5 nogil
     bearer parser → Phase 6 fix the 2 known-failing tests from v1.2.83
     → Phase 7 add no-`.so` CI matrix step.
  6. **v1.2.9 target numbers** — conservative (Phases 1+2+3 only):
     FULL HANDLER 1.07 µs → **0.95 µs**, ~6.1x vs FastAPI; optimistic
     (all phases): **0.85 µs**, ~7.0x vs FastAPI.
  7. **Risks and mitigations** — import-overhead regression in Phase 4 has
     a fall-back to Shape B; bench noise mitigated by 5-run medians.
  8. **Out of scope** — Starlette 1.0, pytest 9, typer 0.25, CI-version
     matrix all deferred.
  9. **9 PRs concretely sequenced** for v1.2.9 with expected delta per PR.

### Verification

- 360/361 framework tests still pass (no code touched).
- `docs/cython-plan-v1.2.9.md` renders correctly.
- `pyproject.toml` bumped to `1.2.84`.

### v1.2.8x phase summary

With this release, the v1.2.8x audit / Cython prep phase closes:

| Sub-version | Deliverable |
|---|---|
| v1.2.81 | `example/` modernized to showcase every v1.2.x feature |
| v1.2.811 + v1.2.812 + v1.2.813 | Two framework bug fixes + example test-runner fix discovered while modernizing the example |
| v1.2.82 | README + `docs/` refreshed for v1.2.x state; new `16-cython-build.md` |
| v1.2.83 | `audit-v1.2.83.md` (coverage, API surface, deps, compat, debt, baseline perf) |
| **v1.2.84** | **`cython-plan-v1.2.9.md`** (this) — sprint roadmap |

**Cleared to start v1.2.9 with Phase 1.**

---

## [1.2.83] — 2026-05-22

**v1.2.8x project audit / Cython prep — sub-version 3/4: project-level audit.**
No framework code changes.  Produces `docs/audit-v1.2.83.md` consolidating the
state of the codebase on six axes (coverage, API surface, deps, compatibility,
tech debt, performance baseline) — feeds v1.2.84's Cython impact analysis.

### Added

- **`docs/audit-v1.2.83.md`** — single-file audit report with sections:
  1. **Test coverage** — 76% overall; per-module breakdown; note on Cython
     shadowing 12 hot-path modules at 0% (measurement artifact, not gap).
  2. **Public API surface map** — every importable symbol per sub-package;
     identifies 4 modules (`background`, `di`, `files`, `testing`) that leak
     typing-import helpers because they don't declare `__all__`.
  3. **Dependencies status** (`poetry show --outdated`) — splits into risky
     (`starlette 1.0`, `pytest 9`, `typer 0.25`), safe minor (`msgspec`, `orjson`,
     `uvicorn`, `pytest-asyncio`, `python-multipart`, `ruff`), and trivial transitive.
  4. **Compatibility matrix** — declared Python `^3.10`, only `3.10.0` actually
     tested; no CI matrix.
  5. **Tech debt inventory** — `grep TODO/FIXME/XXX/HACK` returns zero matches
     (cleaned in v1.2.7); 2 known-failing tests root-caused:
     * `tests/test_cli.py::TestNewCommand::test_new_creates_project_structure` —
       the test hard-codes `my-api` but the CLI normalises to `my_api`. 1-line
       test fix.
     * `example/tests/test_verification.py::test_start_enhanced_verification` —
       cross-test state leak through the example's process-wide verification
       store. Example-only fix via `autouse` reset fixture.
  6. **Benchmark baseline** — 5-run median across the key hot-path metrics
     (FULL HANDLER **1.07 µs**, body POST 0.80 µs, response dict 0.72 µs);
     trend across v1.1.0 → v1.2.82 confirms no regression.

### Findings flagged for v1.2.84 / v1.2.9

- The 4 `__all__`-missing modules: trivial fix, defer if v1.2.9 prioritises.
- Add a "no-`.so`" CI step to measure pure-Python fallback coverage of the
  hot path (the Cython-shadowed 0% rows in §1).
- `middlewares/security_headers.py` at 17% — add unit tests.
- The 2 broken tests fixed in v1.2.9.

### Verification

- 360/361 framework tests still pass.  16/17 example tests still pass.
- Audit report rendered correctly (markdown).
- `pyproject.toml` bumped to `1.2.83`.

---

## [1.2.82] — 2026-05-22

**v1.2.8x project audit / Cython prep — sub-version 2/4: refresh README + docs/.**
No framework code changes.  Brings the public documentation in line with everything
that landed during v1.2.x, including the SRP refactor and the v1.2.811 fixes.

### Documentation (docs only)

- **`README.md`**:
  - Version badge `1.1.0` → `1.2.x`; tests badge `233` → `366 passed`.
  - Feature matrix expanded with DI scopes, WebSocket DI + typed paths,
    `Body(List[Struct])`, `SecurityHeadersMiddleware`, async `create_client`,
    and a new "Architecture" row pointing at the 63-module SRP layout.
  - New top-level **Architecture** section with an ASCII flow diagram of the
    request hot path (`Tachyon.__call__ → ASGIEntry → HTTPDispatcher →
    TachyonDispatcher → handler closure → response`).
  - DI snippet shows all three scopes (`singleton`, `request`, `transient`).
  - WebSocket snippet uses typed `room_id: uuid.UUID` and an injected
    `RoomBroadcaster`.
  - Testing snippet shows the modern `create_client` async pattern.
  - KYC demo summary updated (17 tests, async tests, exception handler).
  - Docs table adds a link to the new `16-cython-build.md`.

- **`docs/README.md`** (index): version `0.7.0` → `1.2.x`, "Why Tachyon?" table
  expanded with routing, DI scopes, OpenAPI capabilities. New entry for
  `16-cython-build.md`.

- **`docs/02-architecture.md`**: appended a *Tachyon's Internal Architecture*
  section enumerating the 63 SRP modules across `app/`, `processing/`,
  `responses/`, `openapi/`, `security/`, and which paths are hot vs cold.

- **`docs/03-dependency-injection.md`**: new section on **scopes** with the
  decision matrix (singleton / request / transient); explicit notes on async
  `Depends` and the v1.2.811 `exception_handler` subclass dispatch fix;
  summary table updated.

- **`docs/10-websockets.md`**: new sections **Typed Path Params** (UUID
  auto-conversion + 1008 on mismatch) and **DI in WebSocket handlers** (covers
  `@injectable` and `Depends(callable)` per-connection).

- **`docs/11-testing.md`**: `create_client()` documented as the canonical
  async helper with the full set of httpx kwargs (`headers`, `cookies`,
  `auth`, `follow_redirects`, `timeout`); `AsyncTachyonTestClient` kept as the
  class-based equivalent.

- **`docs/14-migration-fastapi.md`**: new **v1.2.x Gotchas** section
  covering CORS opt-in, `max_body_size` default 2 MB, `SecurityHeadersMiddleware`
  opt-in, sanitized `UploadFile.filename`, and the v1.2.811 exception-handler
  subclass dispatch. `@injectable` paragraph mentions the three scopes;
  async-test example now uses `create_client`.

### Added (docs only)

- **`docs/16-cython-build.md`** (new): when and how to compile `[fast]`.
  Covers `pip install tachyon-api[fast]` + `python setup.py build_ext --inplace`,
  the list of compiled extensions, fallback behavior, expected perf delta,
  compiler-flag overrides, troubleshooting, and forward reference to the
  v1.2.9 Cython sprint roadmap.

### Verification

- 366/367 framework tests pass (unchanged, no code touched).
- 16/17 example tests pass (unchanged).
- Documentation links validated by direct file existence (`docs/16-cython-build.md`).

---

## [1.2.813] — 2026-05-22

**Remove example workarounds now that v1.2.811 fixed the underlying framework
bugs.** The example now showcases the v1.2.0 features *directly* — no
wrappers, no internal dispatch tricks.

### Reverted (example only)

- **`modules/customers/customers_controller.py::bulk_create_customers`** —
  parameter restored to `customers: List[CustomerCreate] = Body(...)`.
  This was using a `BulkCreateRequest` wrapper as a workaround for the
  decoder bug fixed in v1.2.811.

- **`modules/customers/customers_dto.py`** — `BulkCreateRequest` Struct
  removed. It existed only to sidestep the broken `Body(List[Struct])`
  decoder and has no remaining use.

- **`app.py::kyc_exception_handler`** — registered for `KYCException`
  again (was registered for `HTTPException` as a workaround for the
  dispatch bug fixed in v1.2.811). The handler body shrinks from a
  two-branch `isinstance` dispatch to a single formatter for the
  KYC hierarchy. `HTTPException` import removed.

- **`README.md`** — "Known limitations" callout removed; the workaround
  notes in the feature matrix are replaced with the direct-usage
  descriptions. `⭐ = new or revised in Tachyon v1.2.x` (was v1.2.0,
  now spans v1.2.811 too).

### Verified

- 366/367 framework tests pass (`pytest tests/`).
- 16/17 example tests pass (`pytest example/tests/`). The single failure
  is the pre-existing `test_start_enhanced_verification` cross-test
  state issue tracked in v1.2.83 audit, unrelated to this PR.
- End-to-end smoke (`TestClient`):
  - `GET /customers/me` (no auth) → 401, body `{"code": "UNAUTHORIZED"}`
    via the now-direct `@app.exception_handler(KYCException)`.
  - `POST /customers/bulk` with a JSON array → 200, returns the array
    via direct `Body(List[CustomerCreate])` decoding.
  - OpenAPI: `/customers/bulk` requestBody schema =
    `{"type": "array", "items": {"$ref": "#/components/schemas/CustomerCreate"}}`
    (no wrapper Struct).

---

## [1.2.812] — 2026-05-22

**Fix the example test runner.**  Companion to v1.2.811: brings `pytest example/tests/`
back to a green collection so the v1.2.83 audit has a working baseline.

### Fixed

- **`example/tests/` collection** — pytest 8.x + `pytest-asyncio 0.23.x` raise
  `AttributeError: 'Package' object has no attribute 'obj'` during collection
  whenever any ancestor of the test file is a Python package. The framework's
  own `tests/` directory has no `__init__.py` and so was unaffected; the
  `example/` tree has `__init__.py` everywhere (for the relative imports in
  the app code), so its tests never collected.

  Two-part fix:
  1. **Remove `example/tests/__init__.py`** — the test directory does not need
     to be a sub-package of `example/`.  pytest discovers tests by file name,
     not by package membership.
  2. **Switch test-file imports from relative to absolute**: `from ..app import app`
     → `from example.app import app` (and similarly for `..config`, `..modules.*`).
     Affected files: `conftest.py`, `test_async_client.py`, `test_customers.py`,
     `test_verification.py`. `test_auth.py` had no imports.

- **`example/requirements.txt`** — bump `pytest-asyncio>=1.1.0` (was `>=0.23.0`).
  The 0.23.x line carries the Package-collector bug; 1.1.0+ fixes it.
  The framework's own `pyproject.toml` already requires `^1.1.0`.

### Verified

- `pytest example/tests/` now collects 17 tests and runs them; 16/17 pass.
- The single remaining failure (`TestVerificationEndpoints.test_start_enhanced_verification`)
  is a pre-existing domain-logic issue in the example: `VerificationService.start_verification`
  reuses an in-progress verification when one already exists for the customer,
  so the second test in the class re-uses the first test's `standard`
  verification (3 checks) instead of creating an `enhanced` one (5 checks).
  Tracked as a v1.2.83 audit finding — out of scope for the test-runner fix.
- Framework suite still 366/367.

---

## [1.2.811] — 2026-05-22

**Framework bug fixes discovered during v1.2.81 example modernization.**
Two v1.2.0 features were documented as working but only half-implemented at
the runtime layer — surfaced when porting the example to use them directly.

### Fixed

- **`Body(List[Struct])` decoding** — `processing/compiler.py` and
  `processing/compiler.pyx` (`_build_typed_descriptor`) now attempt to build
  a `msgspec.json.Decoder` for any `KIND_BODY` annotation, not just direct
  Struct subclasses.  Previously, `List[Struct]`, `Optional[Struct]`,
  `Tuple[...]`, and other msgspec-supported generics produced `decoder=None`,
  causing the body extractor to return `"Body type must be a Struct subclass"`
  at request time — even though the OpenAPI spec generated correctly.

  Implementation: wrap the decoder construction in `try/except Exception` so
  msgspec itself decides which types are decodable; unsupported types still
  leave `decoder=None` and surface the same 422 at request time.

  Cython recompiled (`python setup.py build_ext --inplace`).

- **`@app.exception_handler` for HTTPException subclasses** —
  `app/_exception_table.py::dispatch` now walks every registered handler in
  registration order and returns the first `isinstance` match, falling back
  to the default `{"detail": ...}` body only when no handler matched **and**
  the exception is an `HTTPException`.

  Previously, the dispatch short-circuited to the default response for any
  `HTTPException` whenever no handler was registered for `HTTPException`
  itself — so a handler registered for a subclass like
  `MyDomainError(HTTPException)` was never invoked.  The example's
  `@app.exception_handler(KYCException)` was a no-op for this reason.

  Backward-compatible: a handler explicitly registered for `HTTPException`
  still wins because it appears in the registration-order walk; plain
  `HTTPException` instances with no subclass handler still get the default
  body.

### Added

- **`tests/test_v1_2_811_fixes.py`** — 6 regression tests covering:
  - `Body(List[Struct])` happy-path decoding
  - `Body(List[Struct])` validation-error path (422)
  - `Body(Optional[Struct])` decoding
  - `@app.exception_handler(HTTPException-subclass)` invocation
  - Plain `HTTPException` still uses the default body when no handler is registered
  - Explicit `@app.exception_handler(HTTPException)` still wins over the default

### Verified

- 366/367 tests pass (the +6 new tests; pre-existing CLI failure unchanged).
- Test suite passes in **both** modes: with compiled Cython `.so` loaded
  (production) and with the `.so` files moved aside (pure-Python fallback).
- `FULL HANDLER` cycle 1.03–1.11 µs across 3 runs, `process_parameters body POST`
  0.79–0.82 µs — within noise of v1.2.81 baseline.

### Compiled artifacts updated

- `tachyon_api/processing/compiler.cpython-310-darwin.so`
- `tachyon_api/processing/compiler.c`

---

## [1.2.81] — 2026-05-22

**v1.2.8x project audit / Cython prep — sub-version 1/4: modernize `example/`.**
No framework code changes. Updates the bundled KYC demo to exercise every
feature added through the v1.2.x cycle so users have a concrete reference for
the modern idioms.

### Added (example only)

- **`example/shared/request_context.py`** — `@injectable(scope="request")`
  `RequestContext` carrying a per-request `correlation_id` + freeform attributes.
- **`example/shared/id_generator.py`** — `@injectable(scope="transient")`
  `IdGenerator` with sequenced + UUID outputs. Fresh instance per injection.
- **`example/modules/admin/`** — new module showcasing v1.2.0 WebSocket DI:
  - `admin_ws.py` — `@router.websocket("/admin/ws/rooms/{room_id}")` with
    `room_id: uuid.UUID` (typed path param, auto-converted; malformed UUID
    closes connection with code 1008 before the handler runs), `Depends(AdminBroadcaster)`
    (injectable singleton), and `Depends(get_optional_user)` (callable factory).
- **`example/modules/customers/customers_controller.py`** — two new endpoints:
  - `POST /customers/bulk` — bulk create using a `BulkCreateRequest` wrapper
    struct holding `List[CustomerCreate]`, with `RequestContext` (request-scoped)
    and `IdGenerator` (transient) injected.
  - `GET /customers/recent` — declares `response_model=List[CustomerResponse]`
    directly, producing an array response schema in `/openapi.json`.
- **`example/tests/test_async_client.py`** — async integration tests using
  `tachyon_api.testing.create_client` with httpx kwargs (`headers`,
  follow_redirects, etc.).

### Changed (example only)

- **`example/app.py`**:
  - Added `SecurityHeadersMiddleware` to the middleware stack with documented
    opt-in defaults (HSTS and CSP left commented for site-specific setup).
  - Switched CORS from `allow_origins=["*"]` to an explicit allow-list,
    reflecting the v1.2.0 opt-in-by-default change.
  - Registered `@app.exception_handler(HTTPException)` that dispatches by
    `isinstance(exc, KYCException)` (workaround for the dispatch limitation
    captured below).
  - Bumped header `version` from `"1.1.0"` to `"1.2.0"`.
  - Registers the new `admin_router`.
- **`example/modules/customers/customers_dto.py`** — added `BulkCreateRequest`
  wrapper struct.
- **`example/requirements.txt`** — bumped `tachyon-api>=1.2.7` (was `>=0.7.0`).
- **`example/README.md`** — feature matrix marks v1.2.0 additions with ⭐; new
  "Known limitations" section documents the audit findings below.

### Discovered (v1.2.83 audit findings — deferred)

While modernizing the example, three issues surfaced that are out of scope for
v1.2.8x (which is audit-only, no fixes) and will be tracked in the v1.2.83
audit report:

1. **`Body(List[Struct])` runtime failure.** `processing/compiler.py` only
   builds a msgspec decoder when the body annotation is a direct Struct
   subclass — generic `List[Struct]` annotations get `decoder=None`, causing
   `_decode()` in `_extractors/body.py` to return `"Body type must be a Struct
   subclass"`. The OpenAPI spec generation in v1.2.0 (PR #30) handles
   `List[Struct]` correctly, so the spec promises array bodies that the runtime
   then rejects. **Workaround in this example**: wrap in `BulkCreateRequest`.
2. **`@app.exception_handler(HTTPException-subclass)` never fires.**
   `app/_exception_table.py::dispatch` short-circuits to the default response
   for any HTTPException unless a handler is registered for `HTTPException`
   exactly — subclass handlers (e.g., `KYCException`) are never consulted.
   **Workaround in this example**: register for `HTTPException` and dispatch by
   `isinstance` inside the handler.
3. **`pytest example/tests/` fails to collect.** pytest 8.x + pytest-asyncio
   0.23.x raises `'Package' object has no attribute 'obj'` during collection
   when the test directory is a package with `__init__.py`. Affects both the
   pre-existing tests and the new `test_async_client.py`. Test bodies are
   correct; only the runner is broken.

### Verification

- 360/361 framework tests still pass (`pytest tests/ -q`).
- Manual end-to-end smoke through `TestClient` confirms each new endpoint
  responds 200 and emits the expected response shape (verified in PR body).
- `/openapi.json` renders `BulkCreateRequest` with a nested `customers: array`
  property, and `/customers/recent` with `{"type": "array", "items": {"$ref": ...}}`.

---

## [1.2.7] — 2026-05-22

**Closing pass v1.2.7 of the SRP / Cython-readiness roadmap.** Final audit
to confirm the codebase is ready for v1.3.x Cython compilation: `__slots__`
on every hot-path class, type hints on every method, and clean separation
between hot and cold path imports.

### Refactor

- **`__slots__` added to the 5 hot-path classes that were still missing them:**
  - `responses/_json_response.py::TachyonJSONResponse` → `("_send_start", "_send_body")`
  - `responses/_bytes_response.py::TachyonBytesResponse` → `("_send_start", "_send_body")`
  - `responses/_internal_error.py::_InternalErrorResponse` → `("_send_start", "_send_body")`
  - `core/websocket.py::WebSocketManager` → `("_router",)`
  - `app/__init__.py::Tachyon` → 26-slot manifest covering configuration, all
    composed collaborators, DI state, and the HTTP-method-shorthand attributes
    bound via `setattr()` in `__init__`.

  All hot-path classes now declare `__slots__`, matching the v1.3.x cdef
  migration target.

- **Corrected outdated comment in `_json_response.py`** that claimed Starlette's
  `JSONResponse` declared `__slots__` (it doesn't). The subclass can and now
  does declare its own slots for the added attributes.

### Import discipline

- Verified hot-path packages (`app/`, `processing/`, `responses/`, `routing/`,
  `core/websocket.py`) do not import from cold-path packages (`openapi/`,
  `security/`, `cli/`), with one expected exception: `app/__init__.py`
  imports `OpenAPIConfig`/`OpenAPIGenerator`/`create_openapi_config` to wire
  the facade. That import runs once at construction; the per-request hot
  path (`ASGIEntry → HTTPDispatcher → trie dispatcher → handler closure`)
  never touches OpenAPI.

### Verification

- 360/361 tests pass (same pre-existing CLI failure).
- FULL HANDLER cycle stable at **1.04–1.07 µs** across 5 runs, matching v1.2.6
  baseline (within measurement noise).

### v1.2.x roadmap status

With v1.2.7 the SRP refactor pass is complete. Summary of what landed:

| Version | Module | Outcome |
|---|---|---|
| v1.2.1 | `app.py` | 477 lines → 13 atomic modules |
| v1.2.2 | `processing/parameters.py` | 266 lines → 10 atomic extractors |
| v1.2.3 | `responses.py` | 209 lines → 9 atomic modules |
| v1.2.4 | `processing/dependencies.py` | 132 lines → 7 atomic modules |
| v1.2.5 | `openapi.py` | 500 lines → 13 atomic modules |
| v1.2.6 | `security.py` | 169 lines → 11 atomic modules |
| v1.2.7 | Audit pass | `__slots__` + type hints + import discipline |

**Total:** 1753 monolithic lines decomposed into 63 atomic SRP modules.
The codebase is now ready for v1.3.x Cython compilation per the mapping table
documented in `ROADMAP.md`.

---

## [1.2.6] — 2026-05-22

**Refactor pass v1.2.6 of the SRP / Cython-readiness roadmap.** No behavior changes,
no API breaks. `security.py` (169-line monolith with 4 auth schemes + 2 credential
types + a helper parser) is decomposed into 11 atomic modules — one per scheme,
one per credential class, plus the shared bearer parser.

### Refactor

- **`security.py` → `security/` package** with one file per auth concept:

  | Module | Responsibility |
  |---|---|
  | `_bearer_credentials.py` | `HTTPAuthorizationCredentials` value object |
  | `_basic_credentials.py` | `HTTPBasicCredentials` value object |
  | `_bearer_parser.py` | `parse_bearer_header()` — pure function (cdef + nogil candidate) |
  | `_http_bearer.py` | `HTTPBearer` scheme |
  | `_http_basic.py` | `HTTPBasic` scheme (base64 decoding + WWW-Authenticate) |
  | `_api_key_base.py` | `_APIKeyBase` ABC |
  | `_api_key_header.py` | `APIKeyHeader` |
  | `_api_key_query.py` | `APIKeyQuery` (with security warning docstring) |
  | `_api_key_cookie.py` | `APIKeyCookie` |
  | `_oauth2_bearer.py` | `OAuth2PasswordBearer` |
  | `__init__.py` | Re-exports the 8 public symbols |

  Public API unchanged: every symbol previously importable from
  `tachyon_api.security` remains importable from the same path.

### Notes for v1.3.x

- Security is **lukewarm path** (runs only when an endpoint declares auth).
- `parse_bearer_header()` (pure string-parsing function) is the only direct
  Cython candidate — small, stateless, memchr-friendly with `nogil`.
- Auth scheme classes stay pure Python; the bottleneck in their `__call__` is
  `request.headers.get(...)` which is already C-level in Starlette.

---

## [1.2.5] — 2026-05-22

**Refactor pass v1.2.5 of the SRP / Cython-readiness roadmap.** No behavior changes,
no API breaks. `openapi.py` (500-line monolith mixing 6 concerns: config dataclasses,
HTML rendering for 3 UIs, JSON Schema builders, route operation builder, factory)
is decomposed into a 13-module package.

### Refactor

- **`openapi.py` → `openapi/` package** with one responsibility per module:

  | Module | Responsibility |
  |---|---|
  | `_info.py` | `Contact`, `License`, `Info` dataclasses |
  | `_server.py` | `Server` dataclass |
  | `_config.py` | `OpenAPIConfig` dataclass + `to_openapi_dict()` |
  | `_factory.py` | `create_openapi_config()` flat-kwargs factory |
  | `_format_map.py` | `_OPENAPI_FORMAT_MAP` (datetime/UUID format hints) |
  | `_safe_json.py` | `_safe_json()` HTML-safe JSON encoder for `<script>` embedding |
  | `_struct_schemas.py` | `_schema_for_python_type`, `_generate_struct_schema`, `build_components_for_struct` |
  | `_param_schemas.py` | `_scalar_schema`, `build_param_schema` |
  | `_route_builder.py` | `RouteOperationBuilder` — builds `operation` dict per route |
  | `_generator.py` | `OpenAPIGenerator` — spec state + delegates to builder + renderers |
  | `_swagger_html.py` | `SwaggerUIRenderer` |
  | `_redoc_html.py` | `RedocRenderer` |
  | `_scalar_html.py` | `ScalarRenderer` |
  | `__init__.py` | Re-exports the public surface (all dataclasses + generator + schema helpers) |

  Public API unchanged: every symbol previously importable from
  `tachyon_api.openapi` remains importable from the same path.

### Notes for v1.3.x

- OpenAPI is **cold path** (runs only on startup + `/docs` and `/openapi.json`
  requests). No Cython migration planned — the split is purely for SRP and
  testability.
- Each HTML renderer is now an independent class, making future UI swaps
  (Swagger v6, alternative themes) a single-file change.

---

## [1.2.4] — 2026-05-22

**Refactor pass v1.2.4 of the SRP / Cython-readiness roadmap.** No behavior changes,
no API breaks, no perf regression. `processing/dependencies.py` (132-line monolith
with 2 methods mixing 7 responsibilities) is decomposed into a 7-module pipeline
under `processing/dependencies/`.

### Refactor

- **`processing/dependencies.py` → `processing/dependencies/` package**, one
  responsibility per module:

  | Module | Responsibility |
  |---|---|
  | `_sig_cache.py` | `_SIG_CACHE` + `get_signature()` — global `inspect.signature()` cache |
  | `_override_lookup.py` | `OverrideLookup` — "is there a registered override for this key?" (reads `app.dependency_overrides` lazily) |
  | `_scope_cache.py` | `ScopeCache` — singleton/request/transient lookup + store |
  | `_circular_detector.py` | `CircularDetector` — check-and-enter / exit for cycle detection |
  | `_class_factory.py` | `ClassFactory` — instantiates `@injectable` classes with deps resolved |
  | `_callable_factory.py` | `CallableFactory` — invokes `Depends(callable)` async-aware |
  | `_resolver.py` | `DependencyResolver` — orchestrator composing the pipeline |
  | `__init__.py` | Re-exports `DependencyResolver` + `_SIG_CACHE` |

  Public API unchanged: `DependencyResolver(app)` with `resolve_dependency()`
  and `resolve_callable_dependency()` works identically.

### Notes for v1.3.x

- `OverrideLookup`, `ScopeCache`, `CircularDetector`, `ClassFactory` → direct
  `cdef class` candidates (all sync, typed attributes ready).
- `CallableFactory` stays pure Python (async = `await` interplay with Cython
  is more limited; perf gain unclear).
- `_SIG_CACHE` stays as a module-level dict (already C-level lookup at runtime).

---

## [1.2.3] — 2026-05-22

**Refactor pass v1.2.3 of the SRP / Cython-readiness roadmap.** No behavior changes,
no API breaks, no perf regression. `responses.py` (209-line monolith mixing 4
concerns) is decomposed into a 10-module package; the public import surface is
preserved through `responses/__init__.py` re-exports.

### Refactor

- **`responses.py` → `responses/` package** with one responsibility per module:

  | Module | Concern |
  |---|---|
  | `_constants.py` | Protocol identifiers — ASGI message type strings, header name bytes |
  | `_caches.py` | Precomputed lookup tables (`_CL_CACHE`, `_CL_TUPLE_CACHE`, `_CT_TUPLE`) |
  | `_wire.py` | HTTP/1.1 raw wire bytes for `TachyonServer.transport.write()` |
  | `_json_response.py` | `TachyonJSONResponse` |
  | `_bytes_response.py` | `TachyonBytesResponse` |
  | `_internal_error.py` | `_InternalErrorResponse` singleton + `internal_server_error_response()` |
  | `_success.py` | `success_response()` |
  | `_error.py` | `error_response()`, `not_found_response()`, `conflict_response()` |
  | `_validation.py` | `validation_error_response()`, `response_validation_error_response()` |
  | `__init__.py` | Re-exports the full public surface (Starlette types + Tachyon types + helpers + private symbols consumed by `_server_fast.pyx`/`server.py`) |

  Public API unchanged: `from tachyon_api.responses import success_response, TachyonJSONResponse, HTMLResponse, ...` works identically.

### Cython compatibility

- The compiled `_server_fast.cpython-*.so` imports `_HTTP_CL_PREFIX`, `_HTTP_CRLF`,
  `_HTTP_CT_JSON_CRLF2` from `tachyon_api.responses`. The new `__init__.py`
  re-exports these symbols at the same import path, so the compiled extension
  loads and runs unchanged.

### Notes for v1.3.x

- Response classes are direct `cdef class` candidates — all attributes already
  declared, ASGI dicts pre-built in `__init__`.
- Helper functions stay pure Python (cold path).

---

## [1.2.2] — 2026-05-22

**Refactor pass v1.2.2 of the SRP / Cython-readiness roadmap.** No behavior changes,
no API breaks, no perf regression. Compiled Cython (`parameters.cpython-*.so`)
is preserved unchanged — production users running the compiled extension see
zero impact. The pure-Python fallback (`parameters.py`) is rewritten as a
modular pipeline composed of atomic extractors.

### Refactor

- **`processing/parameters.py`** (266-line monolith → ~110-line orchestrator) is
  decomposed into 10 atomic extractor modules under `processing/_extractors/`,
  each answering ONE extraction question with a single public method.

  New atomic modules:
  - `_base.py` — `ExtractorResult` (NamedTuple: `(value, error)`) — uniform return shape
  - `_missing.py` — `missing()` — single source of truth for default-vs-error decision
  - `body_limit.py` — `BodySizeChecker` — content-length + post-read validation
  - `body.py` — `BodyExtractor` — reads body and decodes with msgspec
  - `query.py` — `QueryExtractor` — scalar query parameter
  - `query_list.py` — `QueryListExtractor` — list-valued query (repeated keys + CSV)
  - `header.py` — `HeaderExtractor` — canonical-name header lookup
  - `cookie.py` — `CookieExtractor` — cookie by name
  - `form.py` — `FormExtractor` — form-field by name
  - `file.py` — `FileExtractor` — UploadFile with validation
  - `path.py` — `PathExtractor` — path param with null-byte rejection + type conversion

  Public API unchanged: `ParameterProcessor` from `processing.parameters` retains
  its `process_parameters(compiled, request, dependency_cache)` signature.

  **Both modes verified equal:** test suite passes 360/361 with compiled
  Cython `.so` loaded AND with the `.so` removed (forcing pure-Python fallback).

### Notes for v1.3.x

- The compiled `parameters.pyx` keeps the v1.2.0 single-file Cython logic for
  this release.  v1.3.x will evaluate whether splitting the `.pyx` into
  per-extractor compiled units beats a single-file cdef class (multiple
  `.so` modules add import overhead — TBD by benchmark).
- Each extractor module has `__slots__` declared and full type hints — direct
  `cdef class` candidates.

---

## [1.2.1] — 2026-05-22

**Refactor pass for Cython migration readiness.** No behavior changes, no API breaks,
no perf regressions (FULL HANDLER cycle: 1.04 µs vs 1.05 µs in v1.2.0 — within
measurement noise).

### Refactor

- **`app.py` → `app/` package** (477 lines → 13 atomic modules of ≤ 80 lines each).
  The `Tachyon` god-class is decomposed into single-responsibility collaborators
  per the SRP roadmap (v1.2.x). Each collaborator answers one question, has
  `__slots__` declared, and is a direct Cython migration candidate for v1.3.x.

  New atomic modules under `tachyon_api/app/`:
  - `_asgi_handler.py` — `_ASGIHandler` marker class (fast-path tag)
  - `_404.py`, `_405.py` — pre-built ASGI response constants
  - `_registry.py` — `RouteRegistry` ("what routes are registered?")
  - `_exception_table.py` — `ExceptionTable` (register + dispatch + default response)
  - `_handler_factory.py` — `HandlerFactory` (builds request handler closure)
  - `_fast_asgi_factory.py` — `FastASGIFactory` (builds no-param ASGI closure)
  - `_route_installer.py` — `RouteInstaller` (orchestrates trie + registry + openapi)
  - `_docs_routes.py` — `DocsRoutes` (registers /docs /redoc /swagger /openapi.json)
  - `_docs_schemas.py` — `CommonSchemas` (registers default error schemas)
  - `_mw_stack.py` — `MiddlewareStack` (stores user middlewares + builds wrapped app)
  - `_http_dispatch.py` — `HTTPDispatcher` (routes HTTP to trie, WS/lifespan to Starlette)
  - `_asgi_entry.py` — `ASGIEntry` (lazy HTTP-app build + ASGI delegation)
  - `__init__.py` — `Tachyon` facade composing the collaborators

  Public API unchanged: `from tachyon_api import Tachyon` and all decorators
  (`@app.get`, `@app.exception_handler`, etc.) work identically.

### Fixed

- **`tests/test_error_format.py`**, **`tests/test_response_model.py`** — assertions
  updated to match the secured response from the v1.2.0 audit (`response_validation_error_response`
  no longer leaks internal error details). These tests had been silently failing
  on `dev` since v1.2.0 but were hidden because the test suite ran with `-x`.

---

## [1.2.0] — 2026-05-22

This release completes the **F6–F12 Python/Cython optimisation roadmap** and delivers
a full security + functional audit: path traversal fixes, CORS opt-in, DI scopes,
WebSocket DI, OpenAPI List[Struct], and more.

| Metric | v1.1.0 | v1.2.0 | Δ |
|---|---:|---:|---:|
| Full handler cycle | 1.16 µs | **1.05 µs** | **−9%** |
| `process_parameters` path+query | 0.82 µs | **0.56 µs** | **−32%** |
| `process_parameters` body POST | 1.28 µs | **0.79 µs** | **−38%** |
| Total throughput (100 conns) | 335,626 req/s | **345,046 req/s** | **+2.8%** |
| Speedup vs FastAPI | 5.61x | **5.50x** | (FastAPI also improved) |

### Added

- **`di.py`** — `@injectable` accepts optional `scope` keyword: `"singleton"` *(default, unchanged)*, `"request"` *(one instance per HTTP request)*, `"transient"` *(new instance on every injection)*. Backward-compatible; bare `@injectable` still means singleton. Exports `SCOPE_SINGLETON`, `SCOPE_REQUEST`, `SCOPE_TRANSIENT`.
- **`core/websocket.py`** — WebSocket handlers now support: typed path params (converted via `TypeConverter`; type mismatch closes with code 1008), `@injectable` class deps, and `Depends(callable)` per-connection factories. Param descriptors pre-computed at route registration — zero `inspect` overhead per connection.
- **`openapi.py`** — `generate_route` generates correct schemas for: `response_model=List[Struct]` (array with `$ref`), `Body` with `List[Struct]`, `Form`/`File` params (`multipart/form-data` requestBody with `required` and `format: binary`).
- **`middlewares/security_headers.py`** — New `SecurityHeadersMiddleware`: opt-in, injects `x-content-type-options`, `x-frame-options`, `referrer-policy`, `x-permitted-cross-domain-policies`. HSTS/CSP via constructor params.
- **`testing.py`** — `create_client(app, ...)` promoted to framework public API (was only in `tests/helpers.py`). Accepts httpx kwargs: headers, cookies, auth, follow_redirects, timeout. `AsyncTachyonTestClient` gains the same kwargs.

### Security

- **`files.py`** — `UploadFile` sanitizes `filename` at construction: strips null bytes and directory components to prevent path traversal.
- **`responses.py`** — `response_validation_error_response` no longer echoes internal error details in the HTTP response body; logged at WARNING only.
- **`middlewares/cors.py`** — Defaults changed to `allow_origins=()`, `allow_headers=()`, explicit `allow_methods`. CORS is now opt-in.
- **`security.py`** — `APIKeyQuery` docstring warns tokens in query params appear in logs/history/Referer.
- **`processing/parameters.py`** — Path params containing `\x00` (null bytes) rejected with 422.

### Fixed

- **`background.py`** — `BackgroundTasks.run_tasks()` logs failures at WARNING with traceback instead of silently swallowing them.
- **`core/lifecycle.py`** — Startup handlers raise `RuntimeError` on failure; shutdown handlers log and continue remaining handlers.
- **`cache.py`** — `RedisCacheBackend.clear()` calls `flushdb()` instead of no-op; falls back to `flushall()`.
- **`security.py`** — `_APIKeyBase._get_raw()` is a proper `@abstractmethod` via `ABC`.
- **`openapi.py`** — `build_param_schema` generates correct schemas for `datetime`, `date`, `uuid.UUID`, and `Enum` subclasses.
- **`cli/templates/service.py`** — `assert True` replaced with `pass` in generated test placeholder; `# TODO:` markers replaced with descriptive comments.

### Performance

- **`processing/response_processor.py`** — Skips `msgspec.convert()` when `type(payload) is response_model`.
- **`processing/dependencies.py`** — `_SIG_CACHE` eliminates `inspect.signature()` per-request for `Depends(callable)` and class deps.
- **`app.py`** — `isinstance(handler, _ASGIHandler)` → `type(handler) is _ASGIHandler` in trie dispatch.

### Changed

- **`app.py` / `processing/parameters.py`** — Default `max_body_size` reduced 10 MB → 2 MB. Override via `Tachyon(max_body_size=...)`.

### Refactor

- **`cli/utils.py`** (new) — `validate_name(name, kind)` extracted from duplicated code in `generate.py` and `new.py`.
- **`processing/parameters.py`** — `_missing_param(p, kind, name)` consolidates 6 repeated default/error patterns.

### Performance (F12b/F12)

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