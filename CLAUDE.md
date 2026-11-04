# Tachyon API — repository guide

## Working rules

- Keep commit authorship with the project owner; do not add assistant co-author trailers.
- Work on a feature/fix/performance branch. Never put in-progress feature work directly on main or dev. Merge features into dev, then releases into main.
- Update CHANGELOG.md whenever the version changes, using dated Keep a Changelog categories.
- Maintain one Python implementation. Run `scripts/quality_cycle.py` with a nonempty module inventory; reject stale native binaries. Cython and parity gates were retired in 1.4.1 preparation.
- Optional development/benchmark tools must not become runtime imports. Keep useful install errors in CLI entry points.
- Treat this guide as repository policy, and code/tests as the source of actual behavior. User instructions take precedence.

## Product and architecture

Tachyon is an ASGI framework using Starlette and msgspec, with FastAPI-inspired decorators. It targets predictable request cost and a small implementation. It does not promise full FastAPI compatibility or a fixed performance multiplier.

- `app/`: registration, request execution, middleware composition and error handling.
- `processing/compiler.py`: registration-time parameter metadata and argument binding.
- `processing/scope.py`, `_request.py`: bounded receive, one Request cache, multipart lifetime.
- `processing/dispatch.py`: HTTP routing relative to `root_path`, preserving inherited mount parameters and the original Request path.
- `processing/dependencies/`: scopes, factories, overrides and resolved signatures. Async resolution offloads synchronous user factories.
- `routing/trie.py`: terminal-specific path parameters and static-priority matching with dead-end fallback.
- `responses/`: JSON construction and request-owned ASGI messages. Share immutable bytes and small header tables, never mutable response singletons.
- `core/`: lifecycle and WebSocket integration with Starlette.
- `openapi/`: msgspec schema adaptation for the explicitly supported OpenAPI 3.0 subset. `app/_docs_routes.py` renders local schema URLs with the request root path and supplies an isolated default-server overlay; explicit configured servers take precedence.
- `server.py`: compatibility runner for standard Uvicorn; there is no direct transport writer.
- `cache.py`: bounded in-memory backend, explicit/global decorator configurations, external client adapters.
- `cli/`, `testing.py`: developer tools. Preserve user files and keep read-only modes read-only.

## Implementation constraints

Do introspection, annotation resolution and decoder construction at registration; runtime-added overrides are prepared when first selected. Keep per-request state owned by that request. Singleton graphs capture only explicit singleton provider classes and configured shared override values; never request/transient providers, Request/WebSocket or per-request factories. Check active construction and current overrides before storing singleton instances. Low-level synchronous resolution is bootstrap-only when the same application serves asynchronously. Synchronous user code runs in a thread pool; async code runs on the event loop. Background work follows response transmission and precedes file cleanup. Do not convert send/stream errors into a second response.

Prefer deleting redundant work to adding abstractions. A helper class is justified by state or a clear boundary, not its name. Keep public compatibility when simplifying internals, or provide an explicit registration error and migration note.

Preserve Python integer and float conversion semantics when evaluating future native code. Avoid unchecked C parsers that truncate or accept different input. Multipart and WebSocket protocols remain delegated to Starlette.

Do not claim a performance win without comparable before/after measurements. Separate async and sync/threadpool workloads, match dependency scopes and payloads, validate responses, record errors and percentiles, and retain raw data. Do not sum rates from separate scenarios as application capacity. Pydantic v2 has a native validation engine; comparisons must measure actual workloads.

## Validation and release

Supported interpreters: Python 3.10–3.13. Run `pytest tests/ example/tests/` with test/example dependencies installed. Verify all package modules load as `.py` inside the intended checkout or installed package. Never allow empty origin checks or residual native binaries.

Build one portable wheel and one sdist without Cython. Rebuild the sdist and test its installed wheel outside the checkout on each available interpreter. Keep the deprecated empty `[fast]` extra for installation compatibility. Do not claim the prepared 1.4.1 is published before index verification. The safe orjson minimum is 3.11.6.

Use [local release checks](docs/quality/local-release.md) when hosted CI is unavailable. Preserve source fingerprints, artifact hashes, installed origins and actual platform/interpreter limits. Historical [1.4.0 evidence](docs/audits/1.4.0/LOCAL_RELEASE.md) describes a different native release; do not rewrite its counts or claim that its configured platforms were exercised.

The [assessment and staged Rust investigation](docs/quality/framework-review.md) record current decisions and dated benchmarks. Keep Starlette, msgspec and the public Python API during this cleanup. Granian can be evaluated as an optional server without silently replacing Uvicorn. No Rust core becomes production code without profiling, behavioral parity, release coverage and agreed performance budgets. New TUI/migration subsystems remain outside scope.
