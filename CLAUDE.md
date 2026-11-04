# Tachyon API — repository guide

## Working rules

- Keep commit authorship with the project owner; do not add assistant co-author trailers.
- Work on a feature/fix/performance branch. Never put in-progress feature work directly on main or dev. Merge features into dev, then releases into main.
- Update CHANGELOG.md whenever the version changes, using dated Keep a Changelog categories.
- Apply behavioral changes to Python and Cython counterparts together. Run `scripts/check_py_pyx_parity.py` and the same regression contracts in both import modes. API parity alone does not establish behavioral parity.
- Optional development/benchmark tools must not become runtime imports. Keep useful install errors in CLI entry points.
- Treat this guide as repository policy, and code/tests as the source of actual behavior. User instructions take precedence.

## Product and architecture

Tachyon is an ASGI framework using Starlette and msgspec, with FastAPI-inspired decorators. It targets predictable request cost and a small implementation. It does not promise full FastAPI compatibility or a fixed performance multiplier.

- `app/`: registration, request execution, middleware composition and error handling.
- `processing/compiler.{py,pyx}`: registration-time parameter metadata and argument binding.
- `processing/scope.{py,pyx}`, `_request.py`: bounded receive, one Request cache, multipart lifetime.
- `processing/dispatch.{py,pyx}`: HTTP routing relative to `root_path`, preserving inherited mount parameters and the original Request path.
- `processing/dependencies/`: scopes, factories, overrides and resolved signatures. Async resolution offloads synchronous user factories.
- `routing/trie.{py,pyx}`: terminal-specific path parameters and static-priority matching with dead-end fallback.
- `responses/`: JSON construction and request-owned ASGI messages. Share immutable bytes and small header tables, never mutable response singletons.
- `core/`: lifecycle and WebSocket integration with Starlette.
- `openapi/`: msgspec schema adaptation for the explicitly supported OpenAPI 3.0 subset. `app/_docs_routes.py` renders local schema URLs with the request root path and supplies an isolated default-server overlay; explicit configured servers take precedence.
- `server.py`: compatibility runner for standard Uvicorn; there is no direct transport writer.
- `cache.py`: bounded in-memory backend, explicit/global decorator configurations, external client adapters.
- `cli/`, `testing.py`: developer tools. Preserve user files and keep read-only modes read-only.

## Implementation constraints

Do introspection, annotation resolution and decoder construction at registration; runtime-added overrides are prepared when first selected. Keep per-request state owned by that request. Singleton graphs capture only explicit singleton provider classes and configured shared override values; never request/transient providers, Request/WebSocket or per-request factories. Check active construction and current overrides before storing singleton instances. Low-level synchronous resolution is bootstrap-only when the same application serves asynchronously. Synchronous user code runs in a thread pool; async code runs on the event loop. Background work follows response transmission and precedes file cleanup. Do not convert send/stream errors into a second response.

Prefer deleting redundant work to adding abstractions. A helper class is justified by state or a clear boundary, not its name. Keep public compatibility when simplifying internals, or provide an explicit registration error and migration note.

Python integers and floats must have the same conversion semantics in both engines. Avoid unchecked C parsers that truncate or accept different input. Multipart and WebSocket protocols remain delegated to Starlette.

Do not claim a performance win without comparable before/after measurements. Separate async and sync/threadpool workloads, match dependency scopes and payloads, validate responses, record errors and percentiles, and retain raw data. Do not sum rates from separate scenarios as application capacity. Pydantic v2 has a native validation engine; comparisons must measure actual workloads.

## Validation and release

Supported interpreters: Python 3.10–3.13. Run `pytest tests/ example/tests/` with test/example dependencies installed. Confirm the imported modules are `.py` for fallback tests and native extensions for compiled tests; the skip-build environment variable does not disable extensions already in the checkout.

Build and install wheels outside the source checkout. Rebuild the sdist, then test its installed wheel. Portable wheels use `TACHYON_SKIP_CYTHON=1`; compilation failures must remain visible. The ordinary hosted test workflow is configured for Python 3.10/3.13 in both modes; the wheel workflow configures all four ABIs across its target platforms. Configuration is not an executed result.

When hosted CI is unavailable, use [the local release process](docs/quality/local-release.md) and retain interpreter/engine origins, full and installed-wheel results, platform limits, artifact hashes and publication verification. Supply each available supported interpreter and record gaps explicitly. The [2026-11-04 release evidence](docs/audits/1.4.0/LOCAL_RELEASE.md) covers all four interpreters in both engines on macOS arm64; it is not evidence of Linux/Windows execution. Keep historical counts and benchmark data dated rather than promoting them to current gates.

Use [the audit](docs/audits/1.4.0/AUDITORIA.md), [implementation status](docs/audits/1.4.0/IMPLEMENTACION.md), [migration guide](docs/17-migration-1.4.md), and [benchmark method](benchmark/README.md) as the current release references. New TUI/migration subsystems are outside this cleanup release.
