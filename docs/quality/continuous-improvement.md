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
4. Run the affected tests, then the complete suite in both engines. Include the
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
python setup.py build_ext --inplace
python scripts/quality_cycle.py --engine native --output /tmp/quality-native.json
```

Use a clean snapshot/environment per interpreter. Run fallback before building
native extensions, or use a separate extension-free snapshot; `--engine python`
does not disable compiled modules already present. The runner rejects a
mismatched loaded engine and records the revision, dirty working tree,
Python/platform, output, exit status and duration of each check. A source checkout
run cannot establish installed wheel correctness: build a portable wheel and a
native wheel from the sdist, install outside the checkout and run the wheel
contracts separately. The [local release orchestrator](local-release.md) supplies
these gates without requiring GitHub Actions. Its per-interpreter environment is
reused for native/portable wheel reinstallation; external test directories and
module-origin assertions prevent checkout imports. Hosted workflows can supply additional platform evidence when executed. Results on another operating system require actual
execution there.

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
Detected documentation drift: [2026-11-04 report](../../2026-11-04_DRIFT_REPORT.md).
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
