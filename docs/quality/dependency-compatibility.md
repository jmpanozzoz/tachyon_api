# Dependency compatibility checks

Keep declared dependency ranges in `pyproject.toml`; keep example tools in its
requirements. A resolved environment and a minimum supported environment are
different checks. Record Python/platform, all installed versions, source hash and
artifact hashes for each run. Never infer an untested dependency range from one
passing lockfile.

For each supported interpreter, validate the normal resolver environment and a
separate environment constrained to declared minima where those distributions
support that interpreter. An unsatisfiable minimum combination is a reported gap,
not a reason to silently replace its versions and label it minimum coverage.

Contracts to exercise on Starlette changes:

- Form parsing, malformed multipart, bounded receive and temporary file cleanup.
- HTTP exception dispatch and errors after response transmission begins.
- Mount/root-path routing and path parameter ownership.
- Lifespan identity, middleware generation and startup/shutdown failures.
- WebSocket routing, dependencies and disconnect behavior.
- Test clients and their optional httpx dependency.

`ManagedRequest._get_form`, the parser's private error-file tracking, delegated
routing and test-client integration need explicit checks. Do not claim private
hooks are stable just because installation succeeds.

Use the [local release](local-release.md) pipeline for source, installed wheel and
rebuilt sdist checks. Add the reference integration suite with PostgreSQL/Redis,
the generator cleanup suite and generated-project tests. Check optional strict
OpenAPI validation both present and missing. Benchmark tools and ORM imports must
not enter ordinary framework HTTP imports.

Before a release, compare the resolved wheel metadata, origins and exported
version-bound evidence. A development release without an audit has null
comparison/validation fields, rather than inherited numbers from 1.4.3.
