# Local release validation — 2026-11-04

GitHub Actions was replaced with isolated local builds and tests on macOS ARM64.
The user authorized publication from this host. Six artifacts are validated:
one portable wheel, one sdist, and native wheels for CPython 3.10–3.13 on macOS
ARM64, tagged `macosx_11_0_arm64`. Linux and Windows native builds were not run.
The portable fallback is available, subject to dependency/platform compatibility.

[1.4.0 is published on PyPI](https://pypi.org/project/tachyon-api/1.4.0/). The [publication receipt](local-release/publication.json) records all six verified remote hashes and the product source commit. After downloading from PyPI, both native and portable wheels passed 174 contracts on Python 3.13.18.

## Additional repair cycle

- Mounted HTTP routing now uses the ASGI route path, preserves inherited dynamic
  mount parameters, and handles prefix boundaries/decoded Unicode correctly.
- Mounted documentation uses the request's schema URL and default server prefix;
  request-specific schema overlays leave the cached schema unchanged. Explicit
  server configuration remains authoritative.
- Unsupported WebSocket endpoint parameter markers fail at registration instead
  of injecting marker objects into user code.
- Thirty-two runtime regressions exercise these contracts. Five additional tests
  require publication to stop before upload when gates fail or artifacts change.

## Evidence and result

The [manifest](local-release/manifest.json) records all 49 successful preparation
checks and the SHA-256 of each upload artifact. Eight full-suite reports retain
source fingerprints, interpreter/platform data and engine origins for all 25
extension siblings. All runtime Python and Cython sources were compared with the
generated wheels/sdist and matched the checkout before publication.

| CPython | Full Python suite | Full native suite | Installed portable | Installed native from sdist |
| --- | --- | --- | --- | --- |
| 3.10.22 | 809 passed | 809 passed | 174 passed | 174 passed |
| 3.11.18 | 809 passed | 809 passed | 174 passed | 174 passed |
| 3.12.16 | 809 passed | 809 passed | 174 passed | 174 passed |
| 3.13.18 | 809 passed | 809 passed | 174 passed | 174 passed |

Each native wheel was compiled independently from the same sdist with
`MACOSX_DEPLOYMENT_TARGET=11.0`, then installed and tested outside the checkout.
The deployment tag is not evidence of testing on macOS 11 itself. The archive
checker verified metadata, compatibility tags, fallback files, native extension
inventory, CLI entry point and RECORD hashes. Twine strict metadata checks and
the upload dry run passed. Third-party/example deprecations remain visible.

| Sustained workload | Duration | Validated requests | Errors | RSS start / peak / end |
| --- | --- | --- | --- | --- |
| Python fallback | 60.01 s | 455,658 | 0 | 34,832,384 / 35,323,904 / 27,688,960 bytes |
| Native | 60.01 s | 481,519 | 0 | 37,535,744 / 38,043,648 / 32,915,456 bytes |

These are eight persistent closed-loop clients, one Uvicorn worker, asyncio/h11,
eight mixed scenarios with exact response validation. RSS is sampled from `ps`;
latency percentiles use a bounded random reservoir. This establishes short-run
stability for these workloads, not absence of leaks, multi-hour endurance or a
production capacity SLA. The two engines were run sequentially on this host;
the counts do not establish a controlled global performance multiplier.

## Reproduction and publication

See [local release instructions](../../quality/local-release.md). Preparation
uses temporary frozen snapshots and retains logs/artifacts under the selected
output directory. The source working tree stays free of generated binaries.
`scripts/publish_local.py` only selects manifest-listed files whose hashes still
match, reads local credentials without putting the token in command arguments,
and verifies published hashes against PyPI after uploading. Publication outcome
is recorded separately; this validation report alone is not proof of an upload.

Remaining coverage: native Linux/Windows, actual older macOS hosts, longer soaks
and external production workloads. The synchronous low-level resolver remains
bootstrap-only when asynchronous serving uses the same application. No ISO
conformity/certification is asserted.
