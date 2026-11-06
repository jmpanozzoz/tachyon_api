# 1.4.3 implementation and evidence

Published release audit. Date: 2026-11-06.
The [publication receipt](PUBLICATION.md) records the verified PyPI/GitHub upload;
the sections below retain the preparation measurements and their limits.
Baseline: `f26f6060e7567260763e20cf09f7537d7f56af40` (1.4.2).

## Plan outcomes

| Item | Outcome |
| --- | --- |
| S01 | Implemented: one lazy user middleware chain per generation, registration order shared across HTTP/WS/lifespan, Tachyon app identity, compatible late-add invalidation. Active scopes retain their generation. |
| S02 | Implemented: canonical docs conflict/path validation, preparation before publication, completion marked last, retry and late overwrite protection. Constructor config/in-place pre-serve field edits supported; config-object replacement rejected explicitly. Installed URLs captured; remote schemas only supply HTML links. |
| S03 | Implemented: unused ParamDescriptor/factory metadata and lookup/introspection methods removed; ClassFactory's active resolver retained. |
| S04 | Implemented: unreachable validation catch/helper removed; original decode error payload retained. |
| S05 | Implemented: private shared JSON byte response base preserves both public sibling types and constructor signatures. |
| S06 | Implemented: JSON-only body checker removed; framework-owned body reads use the current per-request bounded receive limit. Outer middleware remains responsible for its own raw receive usage. |
| S07 | Investigated and bounded fix implemented: registered classes enter class resolution directly, removing one immediate duplicate graph traversal. Persistent graph caching/revision registries deferred to preserve override and lifetime validation. |
| S08 | Evaluated and deferred: the direct CORS behavior matrix shows status/body/default/header/fallthrough differences. A compatibility wrapper would recreate protocol handling; custom CORS remains unchanged. |
| S09 | Implemented: fake optional cache import removed. Configuration warnings and decoration-time global/explicit config behavior retained. |
| S10 | Implemented: unsupported-Python guard, common CI/release test requirements, executable/resolved-version recording and explicit setup/resolution documentation. Checkout environment recreated using supported Python 3.13; prior 3.14 environment preserved outside the repository. |
| S11 | Bounded cleanup implemented: ASGIEntry and duplicate middleware registration wrapper removed. Stateful routing/lifecycle/DI/schema ownership retained; broad collaborator flattening deferred. |
| S12 | Evaluated and deferred: default install deps, dual JSON libraries, build backend, small compatibility facades and portable packaging retained. Historical audits preserved; this file provides the release index. |

The plan's investigations and default deferrals are decisions, not missing
rewrites. The implementation keeps the public API and default installation.
Compatibility corrections are described in the
[migration guide](../../17-migration-1.4.md) and [changelog](../../../CHANGELOG.md).

## Review and reproducibility

- [Initial plan](../../quality/1.4.3-simplification.md),
  [concepts brief](concepts_brief.md), [seven-lens findings](brainstorm-findings.md)
  and [actual reviewer statuses](brainstorm-reviewer-status.json).
- [Bounded implementation review](implementation-review.md): both final reviewers
  completed. Its requirements-fingerprint finding was fixed by adding
  `scripts/test-requirements.txt` to the quality input inventory.
- [Baseline behavior](simplification-baseline.json) and
  [candidate behavior](simplification-candidate.json), with the
  [reproducible probe](simplification_probes.py). Historical baseline JSON is
  unchanged; the probe also tolerates the intentionally removed helper and
  records the new docs conflict error.
- [Baseline DI](di-baseline.json), [candidate DI](di-candidate.json),
  [CORS behavior matrix](cors-matrix.json.gz), and
  [investigation harness](investigate.py). DI timings are batches on a 15-node
  warm singleton and include verification; CORS message differences are not
  automatic security findings.
- [Initial ASGI baseline](asgi-baseline.json) includes driver/validation cost,
  excludes networking and is not a production capacity measure.
- [Validation status](summary.json) records completed checks and actual limits.
  All required local release gates passed for the final runtime bytes.

## Completed validation

| Environment | Source/example tests | Installed wheel | Sdist-rebuilt wheel |
| --- | ---: | ---: | ---: |
| CPython 3.10 | 933 | 229 | 229 |
| CPython 3.11 | 933 | 229 | 229 |
| CPython 3.12 | 933 | 229 | 229 |
| CPython 3.13 | 933 | 229 | 229 |

These are repeated interpreter/install executions, not distinct test contracts.
All 40 gates passed, including Ruff, source origins, wheel/sdist inventories,
source hashes, sdist rebuilds, archive consistency and strict metadata checks.
The [manifest](release/manifest.json) records artifact hashes; the
[compressed gate evidence](release/evidence.tar.gz) retains all 46 logs/reports
without adding dozens of loose evidence files. The original validated package
pair is outside the checkout at `/tmp/tachyon-release-143-publication/dist`.
Python bytes in that wheel match the current package source exactly.

Separate [minimum-runtime Python 3.10](quality-minimum-310.json) and
[lock-constrained Python 3.13](quality-lock-313.json) runs also passed all 930
tests. Their [minimum constraints](minimum-runtime.txt) and
[lock constraints](lock-constraints.txt) are retained. Packages absent from the
lock, including example-only tools, resolved separately; this is not a claim
that every installed package appears in the Poetry lock. The
[current resolved Python 3.13 report](quality-current-313.json) records the actual
current installation. Granian and Uvicorn real-server contracts ran in the
matrix; neither the default server nor installation dependencies changed.

The initial runtime audit had 930 source tests. Publication adds three contracts
for automatic, version-bound evidence export. The lower-bound/lock records above
retain their initial 930-test snapshots; the final publication matrix has 933.
A real-network gate also exposed TCP reset after rejection headers on unread
uploads. The network contract now verifies 422 headers and client reconnection
while allowing that specific reset during error-body delivery. ASGI body limits,
status/payload contracts and runtime bytes are unchanged; deployment behavior is
documented in the migration guide.

## Performance and resource observations

The [ASGI comparison](asgi-comparison.json.gz), driven by
[compare.py](compare.py), alternated five blocks per revision on the same Python
and dependencies. Each block used three batches of 5,000 checked responses per
scenario: 1,200,000 measured responses overall. Final median batch cost changes
span approximately -0.4% to +1.1% across the eight scenarios. This does **not**
demonstrate a general framework speedup. The
[network comparison](network-comparison.json.gz) retains all 48,000 request
latencies across three interleaved blocks per revision, with zero incorrect
responses. Its p95/p99 summaries are medians of block percentiles, not pooled
percentiles. Both tests include client/validation costs and uncontrolled host
contention; neither estimates production capacity.

The measured DI improvement is narrower: explicit cached `Depends(Class)` on a
15-node graph now performs 15 binding visits rather than 30. Direct class
resolution remains at 15 and retains its safety checks. See the raw DI probes;
their timings are isolated microbenchmarks, not whole-application speed claims.

[Lifecycle baseline](lifecycle-baseline.json) and
[candidate](lifecycle-candidate.json), collected with
[profile_lifecycle.py](profile_lifecycle.py), separately cover synchronous
endpoints/factories, two middleware layers, 1,000 registered routes, streaming,
declared body rejection and disconnection finalization. The declared rejection
experiment first exposed unnecessary Request allocation. The final shared
scope guard rejects before allocating it: about 5.2 µs versus 9.6 µs in the
intermediate candidate and 4.9 µs at baseline in these batches. The small
remaining rejection cost is recorded rather than hidden. Baseline/candidate
[routing probes](routing-baseline.json) / [routing probes](routing-candidate.json)
also exercise 1,000 and 10,000 routes, including misses and overlapping branches;
the router implementation itself is unchanged.

The final [load/rest observation](endurance.json.gz) completed 664,129 correct
responses, zero errors, in 60 seconds of active load plus three five-second
idle periods (75.3 seconds elapsed). Open descriptors returned from 15 under load
to the baseline seven after each cycle. RSS rose from 41,500,672 to 42,336,256
bytes; the last idle steps each added 32 KiB. This short observation alone
does not establish a plateau or prove absence of leaks. Resource samples and
methodology remain in the raw report; no multi-hour stability claim is made.

A matching [1.4.2 resource control](endurance-baseline.json.gz) completed 667,582
correct responses with zero errors and also returned to seven idle descriptors.
Its RSS rose from 41,533,440 to 42,385,408 bytes, with idle endpoints of
42,336,256 / 42,385,408 / 42,385,408 bytes. Candidate idle endpoints were
42,270,720 / 42,303,488 / 42,336,256 bytes. These observations show a comparable
warmup-scale footprint in the two trials; they do not isolate a cause or prove
long-duration stability. Large raw JSON is stored losslessly as gzip, with both
compressed and uncompressed hashes in the summary.

[Pre-guard evidence](pre-guard-validation.tar.gz) preserves the earlier
measurements and artifact validation, including the allocation regression that
prompted the final fix. Final evidence uses regenerated artifacts and tests for
the final runtime. The original initial-analysis JSON is unchanged.

All execution reported here is macOS ARM64. Linux and Windows execution, longer
duration stability and numeric performance-budget acceptance remain unclaimed.
This is a reviewed and locally validated source candidate.

## Published-package FastAPI comparison

After publication, an isolated environment installed Tachyon 1.4.3 from PyPI and
FastAPI 0.162.0 / Pydantic 2.14.3. [The benchmark report](fastapi-benchmark.md)
contains the eight scenarios and production assessment;
[machine summary](fastapi-summary.json) and
[raw measurements](fastapi-benchmark.json.gz) retain 240,000 measured responses
with zero errors. Observed scenario throughput ratios range from 1.34× to 1.64×;
they are not a universal multiplier or production capacity forecast.

The [machine publication receipt](publication.json) verifies both remote artifact
hashes. Portable wheel metadata alone does not establish execution on an untested
platform. The immutable tag was not moved after publication.
