# Continuous improvement for 1.4.x

This is the engineering process for this repository. It is not an ISO conformity
assessment or a certification claim. The public abstracts of
[ISO/IEC 25010:2023](https://www.iso.org/standard/78176.html) (product quality),
[ISO/IEC/IEEE 29119-2:2021](https://www.iso.org/standard/79428.html) (test processes),
and [ISO 9001:2026](https://www.iso.org/standard/9001) (organizational quality
management) inform the practices below. No clause-level compliance is asserted;
formal assessment requires the full applicable standards and an organizational scope.

## One bounded repair cycle

1. Record the observed failure, affected contract, severity and reproducible case.
2. Add a regression check at the smallest boundary that demonstrates the defect.
3. Repair the cause. Prefer deleting a branch/cache/duplicate implementation over
   adding another special case when the supported contract permits it.
4. Run the affected tests, then the complete suite on the Python implementation. Include the
   example application: it exercises public integrations and lifecycle behavior.
5. Have a reviewer inspect the changed code and adjacent assumptions. Reopen the
   cycle for every confirmed defect; retain the reproducer and resolution.
6. Update user documentation and this cycle's evidence before closing the item.

Do not keep retrying a green suite without new evidence. Finish a cycle when its
regressions pass and no unresolved critical/high issue remains in its reviewed
scope. Broader release risks remain explicit even when the local cycle is green.

## Reproducible gates

Install the project's development tools and PyJWT for the example tests. Use a
supported interpreter (3.10 through 3.13). From the checkout root:

```sh
ruff check tachyon_api tests benchmark scripts
python scripts/quality_cycle.py --engine python --output /tmp/quality-python.json
```

Use a clean snapshot/environment per interpreter. The runner verifies all Python
module origins, rejects stale native files and records the revision, source
fingerprint, platform and check output. Build the portable wheel and sdist, then
rebuild and test the installed package outside the checkout. The
[local release orchestrator](local-release.md) supplies these gates without
GitHub Actions. Configured workflows establish additional platform coverage only
when they actually execute. Historical native measurements below describe 1.4.0.

## Performance and stability acceptance

Keep an unmodified baseline and candidate on the same host/interpreter/dependencies.
Validate every response before comparing timings. Report throughput, latency
percentiles, error counts and memory methodology separately. For meaningful speed
claims, repeat measurements under equivalent load and retain raw artifacts. Do
not turn noisy shared-runner nanosecond timings into mandatory CI assertions.
An ASGI transport test is not a network-load or long-duration stability test.
`python -m benchmark.run_soak --duration 60 --concurrency 8 --output /tmp/soak.json`
provides real loopback HTTP with exact response validation and process RSS
sampling. Its fixed duration starts after warmup; socket timeouts and graceful
shutdown can extend total runtime. Latency percentiles use a bounded sample;
mean/max cover all requests. See the [benchmark methodology](../../benchmark/README.md).

Before release, exercise real HTTP, concurrent requests, disconnections, multipart
limits/cleanup, dependency overrides, lifecycle, WebSockets and malformed input.
Require zero incorrect responses in the chosen scenarios; document duration,
concurrency, supported platforms and known exclusions. Security isolation and
correct responses take priority over a microbenchmark improvement.

## Traceability and remaining release work

Historical audit: [1.4.0 audit](../audits/1.4.0/AUDITORIA.md).
Detected documentation drift: [2026-11-04 report](../audits/1.4.0/initial-drift.md).
Repair evidence: [current cycle](../audits/1.4.0/CONTINUOUS_IMPROVEMENT.md).

Release requires reviewed changes, documented passing checks for the selected
artifact/platform matrix, published migration notes, and a versioned record of
known limitations. Local builds and installed contracts can supply those checks;
untested platforms must remain explicit. Publishing is a separate action.

The [1.4.0 local release](../audits/1.4.0/LOCAL_RELEASE.md) completed 49 preparation
checks across Python 3.10–3.13 on macOS ARM64: 809 source/example tests per engine
and interpreter, plus 174 installed contracts per portable/native wheel. Two
60-second source-snapshot soaks on Python 3.10 used eight clients, exact responses
and actual RSS samples, with zero errors. These runs establish short local
stability for the selected scenarios. They do not cover Linux/Windows native
execution, older macOS systems or multi-hour production endurance.
[Tachyon 1.4.0 was published](https://pypi.org/project/tachyon-api/1.4.0/#files) as
six artifacts whose remote hashes were verified against the release manifest.
Historical repair-cycle measurements remain historical; the local release record
contains the later matrix and publication evidence.

This workflow does not certify uptime, security, or ISO
compliance, and does not establish a quantitative performance SLA.

## 1.4.2 operational candidate — 2026-11-04

The candidate fixes three observed failures: suspended async stream producers on
transport failure/cancellation; HTTP/1 keepalive reuse after rejecting an unread
oversized body; and exhaustive ambiguous-route traversal for impossible suffixes.
Regression reproducers and results are retained in
[`evidence/1.4.2/`](evidence/1.4.2/). This is preparation evidence, not a publication
record. Final artifact validation and publication are recorded separately in the
[1.4.2 GitHub release assets](https://github.com/jmpanozzoz/tachyon_api/releases/tag/v1.4.2).

One identical portable wheel and sdist passed 40 release checks on macOS ARM64
and 40 on Debian 13 ARM64, using Python 3.10–3.13. Each interpreter passed 904
source/example tests and 207 installed contracts for both the candidate wheel and
the wheel rebuilt from its sdist. The archives retain dependency versions, source
fingerprints, logs and artifact hashes. Source validation revision is `d928d27`;
the subsequent LF checkout policy passed another 904-test macOS run and preserved
all runtime/build bytes in a checkout with `core.autocrlf=true`.

Real-server contracts cover Uvicorn and Granian, client disconnections, partial
and slow uploads, producer/file cleanup order, WebSockets and graceful shutdown
with a request in flight. A Linux Granian oversized-body replay failed 31 of 150
follow-up requests before the fix and zero of 150 after it. Routing precedence
also passed 2,000 generated queries against an independent declarative matcher.

The routing rejection avoids expanding alternatives only when a registered
static suffix proves the request impossible. A deterministic 128-route regression
reduced dictionary accesses from 256 to two. Wildcard-ending routes disable that
shortcut. The suffix index adds registration memory; raw measurements distinguish
this cost from process RSS and from network performance.

The final Linux run validated **26,927,848 requests with zero errors** over
1,800 active seconds, split into three ten-minute loads and three 30-second
rests. Runtime SHA-256 matched the current checkout. Open descriptors returned
to seven after each rest. RSS was 38,506,496 bytes at baseline and 39,550,976,
39,563,264 and 39,571,456 bytes after the rests. The separately archived macOS
endurance run used an earlier runtime and is preliminary evidence only.

Installed-wheel A/B measurements used Python 3.13, identical dependency versions,
and baseline/candidate/candidate/baseline order after stopping the Linux VM.
All 192,000 timed ASGI responses were validated. The table reports medians across
six samples per scenario; driver and response-validation work are included.

| ASGI scenario | 1.4.1 (µs/request) | Candidate 1.4.2 (µs/request) |
| --- | ---: | ---: |
| Hello | 3.802 | 4.068 |
| Path/query | 8.563 | 8.835 |
| Body | 11.654 | 12.058 |
| Nested body | 12.130 | 12.132 |
| Response model | 5.925 | 5.914 |
| Header | 4.917 | 5.048 |
| Dependency | 11.618 | 11.801 |
| Query | 10.022 | 9.823 |

These mixed results do not support a general speedup claim. The minimal case
increased about 7% (0.266 µs); small differences on a shared host are not evidence
of statistical significance. The installed matcher profile at 10,000 routes
measured ordinary static hits at 0.571/0.573 µs and adversarial overlapping misses
at 5.738 ms/0.552 µs (baseline/candidate). Retained Python allocations during
registration increased from 14,564,056 to 15,088,576 bytes, about 3.6%.
This is a bounded worst-case improvement with an explicit memory cost, not an
HTTP throughput multiplier. No new FastAPI network comparison was run here.

The machine-readable [summary](evidence/1.4.2/summary.json), matrix and compressed
logs/reports preserve artifacts, versions, raw timing samples and methodology.

Windows execution, Linux x86-64, multi-worker endurance and multi-hour production
traffic remain untested. The Linux VM had two ARM64 CPUs and 2 GiB RAM with no
host directory mounts. Local loopback load on this shared host establishes the
selected contracts, not a capacity estimate or an absence-of-leaks guarantee.
