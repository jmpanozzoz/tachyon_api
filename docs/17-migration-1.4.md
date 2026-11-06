# Migrating to 1.4

1.4.0 uses the [local release process](quality/local-release.md) when hosted CI is unavailable. Check the release evidence for the tested interpreters and platforms.

1.4 corrects execution and resource ownership contracts. It keeps the decorator API, Starlette integration, msgspec models, and the default installation dependencies.

- Synchronous endpoints, dependency factories, exception handlers and background tasks run in a worker thread. Use `async def` for asynchronous work; singleton services accessed from sync handlers must support concurrent access. Thread offloading adds scheduling cost to trivial sync endpoints and prevents blocking work from stopping the event loop.
- Router, include-router and route dependencies accumulate and share a request cache. Use `Depends(callable)` for guards without a parameter annotation. Untyped `Depends()` in a router list now raises an error instead of being ignored.
- Required endpoint parameters need an explicit parameter marker, a matching path parameter, or an injectable dependency. Unsupported options and signatures fail at registration. Ordinary Python default arguments remain defaults, and keyword-only parameters work.
- Returned response objects and dictionaries are preserved. Background tasks run after the body is sent, before uploaded files are closed. Files belong to the request: copy or persist data before returning if it must outlive that request.
- The default total body limit remains 2 MiB, enforced cumulatively for JSON, forms, files and injected Request reads. Oversized input returns 422. Forms are buffered within that bound before parsing so repeated Request/Body access has a single cache and interrupted reads create no parser files. Starlette multipart field/file limits also apply.
- `tachyon_api.server.run` and `TachyonHTTPProtocol` remain compatibility entry points using standard Uvicorn. The unsafe direct transport writer and its extension were removed. `tachyon_direct_write` returns False for old integrations; the CLI server flag uses standard protocol handling.
- Python 3.10–3.13 is the supported range. 3.14 is excluded until the msgspec version used by Tachyon is validated there. In published 1.4.0, native source builds require a compiler; 1.4.1 removes that build path.
- In 1.4.0, `tachyon-api[fast]` supplies Cython for local builds; in 1.4.1 it is an empty deprecated alias. `[test]` supplies HTTPX. The default install still includes server, CLI and multipart dependencies.
- The in-memory cache defaults to at most 1,024 entries with monotonic TTL and LRU eviction. Use `InMemoryCacheBackend(max_entries=...)` to change capacity. `cache(config=...)` selects an explicit configuration; replacing global configuration does not rebind decorators already created. Cache values are not copied. Redis/Memcached adapters require clients with a deliberate serialization policy.
- Response models validate existing Struct instances and nested values, including fields changed after construction. All validated model outputs use msgspec JSON serialization. Explicit Response objects retain their own serialization contract.
- Default cache keys include a per-decoration namespace. Shared backend entries across workers or restarts require an explicit stable `key_builder`. Backend failures log and fall back to execution; external synchronous backends run in the shared worker pool and must support concurrent calls.
- Multipart filenames discard directory/drive components and NUL bytes; clients must never use them as trusted storage paths. File lists require `list[UploadFile] = File()`. Scalar file fields reject repeated or text inputs; text form fields reject file parts.
- OpenAPI documents wire names, inherited/defaulted msgspec fields and nullable values correctly. This release supports OpenAPI 3.0.x. Conflicting schema component names, fixed-length tuple schemas, constrained mapping-key schemas and unsupported version settings raise explicit errors. Rename conflicting models; unsupported documentation can be excluded with `include_in_schema=False`. Runtime validation remains independent of documentation.
- Dependency factories accept typed Request/WebSocket, nested Depends, registered classes, Python defaults and Header/Query inputs. Other parameter markers in factories are rejected; use Request explicitly. Singleton constructors may capture singleton classes only; request/transient dependencies, Request/WebSocket and per-request callable factories are rejected to prevent lifetime capture.
- Low-level synchronous `DependencyResolver.resolve_dependency` is for bootstrap before serving. Do not mix concurrent synchronous and asynchronous resolution on the same application; dispatch uses asynchronous resolution.
- Generator dependencies are explicitly rejected; use lifespan for managed resources. WebSocket request-scoped dependencies are scoped to the connection, including router guards.
- `lint all --no-fix` checks formatting without rewriting files. `install-skill` updates a managed block and preserves surrounding instructions. `openapi validate` is a limited structural check, not full specification validation.

The benchmark runner compares async workloads with matching dependency scope and response-model inputs. It validates responses and records per-scenario errors and percentiles. Historical summed throughput and framework multipliers are not current performance claims. Retained historical data is labeled with its method and limits; new local results do not establish production capacity.

Mounted HTTP/WebSocket routing preserves inherited mount parameters. Local documentation schema URLs follow each request's `root_path`; external HTTP(S) and network-relative schema URLs keep their configured destinations. A mounted schema response supplies `servers: [{"url": root_path}]` only when no explicit OpenAPI servers were configured. This per-request overlay leaves the cached schema unchanged, so dynamic tenant mounts do not retain another tenant's prefix. CLI-exported schemas have no request-specific overlay.

WebSocket endpoints reject Query, Header, Body, Cookie, Form and File defaults during registration; read typed WebSocket attributes or put Header/Query in a Depends factory. Positional-only WebSocket signatures and required parameters without a binding are also rejected.

The [2026-11-04 local release record](audits/1.4.0/LOCAL_RELEASE.md) distinguishes the eight validated CPython/engine combinations and macOS arm64 publication from the configured hosted Linux/Windows matrix. Check that dated evidence rather than treating a workflow file or historical test count as proof of a new release.

## 1.4.1

Cython implementations and compilation are removed; Python module names and the
public API remain. `[fast]` is an empty deprecated alias. Uvicorn/CLI installation
behavior is retained. orjson now requires at least 3.11.6. Use a clean checkout
for editable builds and restart services after upgrades; residual native files
are rejected by quality/install gates. See [packaging](16-cython-build.md).


## 1.4.2

- An async streaming producer is finalized on send failure or cancellation before
  request-owned files are closed. Failed transmission still skips subsequent
  background tasks and never triggers a second response.
- Oversized bodies keep the existing 422 status. HTTP/1 responses explicitly
  retire the connection when the rejected body was not consumed, preventing
  reuse of an unusable keepalive connection. HTTP/2 receives no added Connection
  header; shared response objects are not mutated.
- A routing prefilter can reject impossible static endings when an ambiguous
  search would begin. Wildcard-ending routes disable that rejection, preserving
  fallback and complete-static-path 405 precedence. Slashes and Unicode retain
  their existing behavior.

These corrections preserve the Python API. Rust, model replacement and server
installation defaults are outside this patch. Platform coverage and durations
belong to the dated validation evidence, not a blanket production guarantee.

## 1.4.3

- User middleware now shares one chain across HTTP, WebSocket and lifespan,
  preserving HTTP registration order. WebSocket/lifespan order now matches HTTP;
  `scope["app"]` and the app passed to user lifespan remain Tachyon.
  Use `app.state` for shared resources; integrations that used Starlette-specific
  app attributes on non-HTTP scopes must use the Tachyon surface instead. Each chain
  generation constructs its middleware once. Late additions rebuild the next
  generation; active requests/lifespan retain their original instances.
- Documentation URLs are validated and handlers prepared before the first scope
  publishes any docs routes. Conflicts with existing GET routes, duplicate docs
  destinations (including fixed `/swagger`), and malformed local paths raise
  `ValueError` instead of silently overwriting handlers. Rename conflicting user
  routes or configure distinct docs URLs. Later GET registrations cannot replace
  installed docs routes. Ordinary user-route replacement behavior is unchanged.
- Supply `openapi_config` to the constructor or edit its fields before the first
  scope. Replacing that object before setup raises a clear error because the schema generator
  and renderers bind it at construction. After setup, the original configuration
  remains bound; replacing it does not reconfigure the installed docs. Installed route/schema-link URLs stay
  bound afterward; changing URL fields does not relocate them. External schema
  URLs remain HTML destinations and no longer become bogus local trie entries.
  Relative local schema URLs such as `schemas/openapi.json` remain supported
  and register at `/schemas/openapi.json`, with mounted HTML links preserved.
- JSON and direct Request reads now use the same per-request body limit. Changing
  a valid integer `app.max_body_size` affects subsequent request scopes for both
  paths. 422 payloads and HTTP/1 retirement/HTTP/2 header behavior are preserved.
  Closing HTTP/1 with unread upload bytes can reset the TCP stream after rejection
  headers; delivery of the error body is transport-dependent. Clients must honor
  `Connection: close` and reconnect. Use an appropriate upload/Expect policy at
  the deployment ingress when handling large requests.
- Both public JSON response classes, default dependencies, CORS behavior and
  cache configuration semantics remain. `Depends(Class)` delegates to the class
  validation path once; pre-cache and post-construction override/lifetime checks
  remain. No persistent DI graph cache is introduced.

See the [candidate evidence](audits/1.4.3/README.md) for actual test environments
and the deliberately deferred CORS/build/dependency restructuring.
