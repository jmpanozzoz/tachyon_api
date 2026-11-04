# Repair and simplification cycles — 2026-11-04

Status: local repair gates passed; 1.4.0 remains unreleased. Changes are on
`feature/v1.4.0-audit-cleanup`, uncommitted. The original audit and drift report
remain historical observations. This report records the subsequent corrections.

## Repairs and independent review

| Cycle | Observed defect or unnecessary work | Resolution and regression evidence |
| --- | --- | --- |
| 1 | Singleton captures request data; Header/Query defaults reach factories as marker objects | Prepared argument bindings reuse existing parameter extractors. Singleton graphs accept only explicitly singleton providers or configured constant overrides. Unsupported lifetimes/markers fail explicitly. `test_continuous_di.py` |
| 1 | Actual multipart objects bypass filename sanitization; repeated File returns a scalar | Normalize parser files while sharing the owned stream; portable basename sanitization; scalar/list annotation and part validation; binary-array OpenAPI. `test_continuous_uploads.py` |
| 1 | Constructed/mutated/nested Struct values bypass response validation | Validate the JSON representation against the response model and encode the validated value. Explicit Response objects retain their own contract. `test_continuous_responses.py` |
| 1 | Closures collide in cache; reads can fail requests; external clients block the event loop | Namespace default keys per decoration; explicit stable custom keys for cross-process reuse; logged fail-open reads/writes; worker offload for synchronous external clients. `test_continuous_cache.py` |
| 1 | Cache set scans every entry | Remove the scan. Bounded LRU writes update the entry and evict under pressure; expired entries are removed on access. No new expiry index or background collector. |
| 2 | File parts passed to text Form fields cause 500 or incorrect typed values | Reject all non-text repeated values before scalar/list conversion. `test_continuous_form.py` |
| 2 | Valid response models containing bytes/Decimal/timedelta cannot use the generic serializer | All validated outputs use msgspec JSON. Existing model instances and nested containers are covered. `test_continuous_responses.py` |
| 2 | Accepted ISO dates change between Python 3.10 and 3.13 | Shared explicit date/datetime grammar, fractional-second normalization and UTC Z normalization. Valid/invalid cases run on both interpreters. `test_continuous_uploads.py` |
| 2 | Shared dependency DAG validation expands exponentially | Separate active-cycle detection and per-call completed states keyed by provider/capture context. A 15-node shared DAG now visits 15 bindings instead of 32,767; checked by operation count, not timing. `test_continuous_di_graph.py` |
| 2 | Concurrent synchronous resolution sees false cycles/duplicate constructors | Context-local resolution stack and per-provider synchronous construction locks. Delete the unused CircularDetector implementations; 25 Python/Cython pairs remain. `test_continuous_di.py` |
| 3 | Overrides changed during singleton construction can capture request values | Enforce capture context during actual construction and selected override invocation; validate before storing. Request override cache entries include selected override identity. Do not switch root factories after waiting on a lock. Deterministic race tests in `test_continuous_di.py` |
| 3 | NaN/infinity can serialize as null against a numeric response model | Validate the wire representation, including nested numeric schemas. `test_continuous_responses.py` |
| 3 | Fractional external TTL becomes zero; Memcached TTL beyond 30 days becomes an expired timestamp | Round positive TTLs to integer seconds; translate long Memcached TTLs to absolute expiration. Test boundaries and both supported client call signatures. `test_continuous_cache.py` |
| 3 | Wheel tests can inherit checkout imports and misidentify the loaded engine | Copy contracts into an isolated temporary directory/config, assert installed origins for all extension siblings and verify the requested engine. Repair missing tests-package initialization and expand wheel CI path triggers. `scripts/test_installed_wheel.py` |

Reviewers inspected changes outside their implementation ownership and returned
reproducers. Each confirmed finding above was repaired and rechecked. The final
DI review passed 94 focused tests in Python 3.10 fallback and 3.13 native with no
remaining confirmed P1 issue in ordinary HTTP handling within that scope. This is
a scoped engineering review, not a proof that the whole framework has no bugs.

## Documentation and DX

Documentation now states implemented marker aliases, model mutability, cache
namespacing, DI lifetime limits, uploads, standard Uvicorn transport and the
production worker default. Historical benchmark multipliers and obsolete internal
inventories were removed. Executable documentation contracts cover code fences,
parameter/tutorial applications, generated CLI scaffolding and assistant examples.
The example also tests secret configuration, real WebSocket messages and lifecycle
events. Existing examples use explicit shared mock instances under singletons.

## Validation evidence

[Machine-readable summary](continuous-validation.json) contains artifact SHA-256
hashes, source fingerprint, check results and exclusions. All four checkout runs
share the same source fingerprint; every one verifies origins for 25 engine modules.

| Environment | Result |
| --- | --- |
| Python 3.10.22, fallback | 772 passed |
| Python 3.10.22, Cython | 772 passed |
| Python 3.13.18, fallback | 772 passed |
| Python 3.13.18, Cython | 772 passed |
| Portable wheel installed outside checkout, Python 3.13 / Starlette 1.10.0 | 142 passed |
| Native wheel rebuilt from sdist, installed outside checkout, same dependencies | 142 passed |
| Ruff 0.14.9, parity and whitespace checks | Passed |

Source validation used Starlette 1.3.1; fresh installed-wheel environments used
1.10.0. Tests passed on this macOS ARM64 host. Third-party deprecations and example
runtime `datetime.utcnow()` warnings remain visible; they are not test failures.
Wheel Python sources and sdist Cython sources were compared byte-for-byte to the
checkout. Portable/native wheels and sdist remain in `/tmp/tachyon-cycle-*`;
durable artifact hashes and test logs are retained here.

[Loopback benchmark](../../../benchmark/results/continuous-1.4.0-native.json):
8 scenarios × 3 applications × 2 repetitions × 200 measured requests = 9,600,
including 3,200 for Tachyon, concurrency 8, zero incorrect responses/errors.
Client validation and connection overhead are included. This is a short controlled
benchmark, not a long-duration soak, production capacity claim or global speedup.

[Fresh fallback import allocation measurement](import-continuous-python313.json):
10,100,944 traced bytes versus the audited baseline's 28,133,797, approximately
64% less. These are Python allocations with tracemalloc, not RSS. Uvicorn remains
absent from the framework import. Runtime source now has 137 files / 8,790 lines
versus baseline 138 / 8,769; correctness checks add necessary code, while removing
modules and work from cache writes and dependency graph validation.

## Continuous gate and remaining limits

[The repeatable quality process](../../quality/continuous-improvement.md) defines
repair, regression, review and closure. CI runs `scripts/quality_cycle.py` on the
minimum/maximum supported interpreters in both engines and retains JSON reports.
Installed wheel checks run in isolation, including all new runtime contracts.

Before publishing: run the hosted Linux/Windows/macOS wheel matrix, a sustained
network load/memory soak, and final release review. Local success does not establish
those results. Low-level synchronous `resolve_dependency` is for bootstrap before
serving; do not mix concurrent synchronous and asynchronous resolution on the same
application. Framework dispatch uses asynchronous resolution. Generator DI,
additional dependency parameter markers, and OAuth2 OpenAPI flow generation remain
explicitly unsupported rather than implied by examples.

ISO references inform traceability, risk-based verification and corrective-action
practice. No ISO conformity, certification or reliability SLA is claimed.
