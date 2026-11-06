# 1.5 development candidate — local evidence

Recorded 2026-11-06. **Not published; not a production-readiness certification.**
The latest stable release remains 1.4.3. The [summary](summary.json) links source,
artifacts and actual validation limits.

## What was implemented

HTTP generator dependencies have request-owned LIFO cleanup, sync thread execution,
explicit failure/cancellation ownership and bounded cooperative cleanup. Singleton
capture restrictions remain; WebSocket/bootstrap generator dependencies are rejected.
The existing KYC example now uses PostgreSQL, migrations, current database identity
and ownership, Argon2id, durable leased jobs, idempotency, Redis and authenticated
notification tickets. The CLI retains its commands and adds diagnostics, tested
minimal/PostgreSQL starters, JSON route inventory and optional strict OpenAPI checks.
Security/support/compatibility/operations and pilot guides accompany the code.

Uvicorn logs WebSocket URLs through its error logger even with access logs disabled.
The reference now supplies a ticket-redacting logging configuration, used by its
Docker command and real-process acceptance driver. Input bounds matching storage
columns produce validation errors before a database failure.

## Source and installed packages

| Python | Final source/example tests | Installed wheel | Wheel rebuilt from sdist |
| --- | ---: | ---: | ---: |
| 3.10 | 1,001 | 255 | 255 |
| 3.11 | 1,001 | 255 | 255 |
| 3.12 | 1,001 | 255 | 255 |
| 3.13 | 1,001 | 255 | 255 |

All execution was on **macOS ARM64**. The package preparation passed 40 gates,
including origins/source-byte comparisons, metadata/archive checks and real-server
contracts. See [the package manifest](package-validation.json) and
[retained logs](validation-logs.tar.gz). The later source matrix includes the
reference logging/input-bound follow-ups; these did not change framework Python
bytes. [Source reports](source-cp313.json) record their own revision, inputs and
resolved dependencies. Source revisions are snapshots before this evidence was added.

The validated pair is a 118,701-byte portable wheel and a 168,350-byte sdist.
SHA256 values and source/runtime fingerprints are in the manifests. The owned
framework contains 105 Python modules / 7,672 lines including comments, templates
and blank lines, versus 102 / 7,163 in 1.4.3. ORM/cache/job integrations remain
reference dependencies, outside the framework's runtime dependency list.

The [lower-bound component environment](lower-bound-compatibility.json) passed the
same 1,001 tests on Python 3.13 with Starlette 1.3.1, msgspec 0.19.0 and orjson
3.11.6. This checks those particular lower bounds, not every possible dependency
combination or every interpreter at all minima.

## Reference, starter and recovery checks

[Two API processes and a separate worker](reference-processes.json) exercised real
TCP HTTP/WebSocket, shared PostgreSQL identity/state, Redis cross-process messages,
redacted server logs and API/worker restart recovery. The final timed run validated
38,003 responses, including expected 422s, with zero unexpected errors. All 3,799
successful verification writes reconciled to completed jobs and one published
event each. See [reconciliation](reference-reconciliation.json) and the
[raw workload/reservoir](reference-business-load.json.gz). The client shared the
host with validation work; these rates are not application capacity or an SLA.

The [PostgreSQL CLI starter](generated-starter.json) was generated from the
validated installed wheel outside the checkout. Its tests, real migration, HTTP
write/validation, process restart persistence and explicit connectivity diagnostic
passed. Reapplying migration head preserved data. It is deliberately smaller than
KYC; generated generic repositories retain their documented in-memory behavior.

A [local backup/restore drill](backup-restore.json) restored the starter into a
separate disposable PostgreSQL database and compared rows and migration revision.
This is not a Linux recovery or compatible application rollback demonstration.
There is no prior persistent reference schema version to upgrade from yet.

The 62 reference tests have a [source coverage report](reference-coverage.json)
excluding test files and migrations. Its combined statement/branch measure is
about 79%; worker/seed entry points exercised in separate processes are not
instrumented by that pytest report. This is not exhaustive endpoint, failure or
security coverage.

## Cost without dependencies

[Raw comparison](no-di-comparison.json.gz), [probe](no_di_probe.py): seven
alternating paired subprocess runs per version, both installed, same runtime
dependencies and CPython 3.13.18. Each run uses 5,000 warmups and 15 shuffled blocks
of 20,000 calls per case; JSON bodies are checked. Medians are computed per process
and then across processes. CPU and wall time are reported separately.

| Case | CPU time change vs 1.4.3 | Wall time change |
| --- | ---: | ---: |
| Plain async response | -0.02% | +1.20% |
| Typed query input | +0.84% | -0.58% |

Both cases stay within the proposed 5% local investigation threshold. These are
ASGI dispatch cost observations, not HTTP capacity, a FastAPI comparison or a
framework-wide speedup. Host CPU frequency/thermal state was uncontrolled. The
[earlier exploratory comparison](exploratory-pre-final-comparison.json.gz) used a
nonfinal source checkout versus an installed baseline with short wall-only runs;
its large dispersion was not used as final acceptance evidence.

## Dependency review and pending gates

The resolved and lower-bound environments were scanned with pip-audit. Their
[reports](resolved-dependency-audit.json) found no known advisories among examined
third-party packages after updating the test harness to pytest >=9.0.3; see the
[pytest advisory](https://github.com/advisories/GHSA-6w46-j5rx-g56g). The unpublished
local framework candidate was skipped by the index-based scanner. No scanner
result establishes absence of vulnerabilities or replaces a code/security review.

[Container manifests](container-manifests.json) were resolved from the official
registry and pinned by digest. Dockerfile/Compose configuration was checked as
source; containers were not built or executed here. GitHub Actions did not start
because the account was locked for billing; configured hosted jobs do not add
platform coverage.

Still pending: the owner's Linux host/access/inventory, installed validation on
that host, Docker execution, representative multi-hour/24-hour loads, calibrated
service budgets, DB/Redis outage and rollback drills on the target, another
architecture/Windows where claimed, and a real participant pilot. The
[implementation plan](../../production-readiness.md) and
[Linux runbook](../../linux-validation.md) retain those acceptance gates.

`SHA256SUMS.json` identifies the retained evidence files. Server logs and database
dumps stay private; public process summaries record the successful checks.
