# EGM documentation drift report — 2026-11-04, after publication

Scope: 31 repository documents, read sequentially within each assigned scope and compared with referenced code, tests, metadata and actual release evidence. Findings below describe discrepancies observed and repaired in this pass; historical audit contents were preserved with status notices. Generated evidence JSON is immutable measurement data, not an active product specification. This applies egm-drift-report, not the separate Goldfish convergence protocol.

## README.md

- Duplicate version badges, unpublished status, incomplete WebSocket handshake example and inaccurate installation/native-platform guidance were corrected; published PyPI and source-branch links now identify actual availability.

## CLAUDE.md

- Instructions conflated configured CI with local release coverage and omitted strict singleton capture/override boundaries. Updated sources, evidence requirements and platform scope.

## CHANGELOG.md

- Release notes omitted graph-traversal complexity, override races, external TTL behavior and local publication tooling. Added those to 1.4.0; post-publication documentation/example work is under Unreleased. Older release history is preserved.

## 2026-11-04_DRIFT_REPORT.md

- Original findings could be mistaken for current unresolved defects. The historical snapshot notice now points directly to the verified published-release record.

## docs/README.md

- Index still called 1.4.0 unreleased and repeated unsupported competitor dependency/complexity comparisons. Replaced with published scope, complete guide links and maintenance/release evidence.

## docs/01-getting-started.md

- Unpublished status, platform availability and a production command requiring an uninstalled event-loop extra were inaccurate. Corrected installation and Body examples.

## docs/02-architecture.md

- Module setup omitted the router export needed by the demonstrated import, and internal file placement was unclear. Corrected both.

## docs/03-dependency-injection.md

No drift detected.

## docs/04-parameters.md

- Body positional metadata examples and the limitations of File list defaults were inaccurate. Corrected to supported marker/default contracts.

## docs/05-validation.md

- Example invalid-body payload omitted the actual error prefix/path. Response-model wire validation, explicit Response bypass and constructor-validation wording were corrected; standalone examples now have their required declarations.

## docs/06-security.md

- An optional Bearer example treated token presence as authentication. It now validates credentials before returning private data; extraction/JWT/OAuth2 responsibilities are explicit.

## docs/07-caching.md

No drift detected.

## docs/08-lifecycle.md

- Cleanup after errors, startup-failure behavior, thread execution and lifespan state were overstated or incomplete. Corrected against the lifecycle implementation.

## docs/09-background-tasks.md

- Completion/cancellation semantics and an arbitrary duration promise were inaccurate. Corrected to actual ASGI task/resource ownership.

## docs/10-websockets.md

- Unsupported endpoint markers were not explicitly rejected in the guide, and the broadcaster example omitted connection cleanup. Corrected examples and mounted-route behavior.

## docs/11-testing.md

- Lifespan and nested singleton override examples did not match supported execution/lifetimes. Corrected fixtures and linked dated source/installed release results.

## docs/12-cli.md

- Route inspection was described more broadly than the HTTP registry it reads; Ruff availability and mounted schema-export context were unclear. Corrected tool scope.

## docs/13-request-lifecycle.md

- Response-model serialization, mounted paths/schema overlays and header-cache behavior lagged behind implementation. Updated pipeline contracts.

## docs/14-migration-fastapi.md

- Guide promised unavailable Linux/Windows native wheels, used MB for MiB, and contained invalid error data and lifecycle/async-client assumptions. Corrected migration examples and optional server configuration.

## docs/15-best-practices.md

- Exception example used a nonexistent errors attribute; integration example sent an invalid Python set and expected the wrong success status. Corrected them, response-model encoding claims, lifetime guidance and platform/loop requirements.

## docs/16-cython-build.md

- Checkout requirements and configured CI jobs were confused with actually validated platforms/interpreters. Corrected build instructions and evidence scope.

## docs/17-migration-1.4.md

- Mounted schema/server defaults, explicit server precedence and unsupported WebSocket markers needed precise migration contracts. Updated published release context.

## example/README.md

- Test inventory, delay range and launch assumptions were stale. Corrected documentation and the executable example first-task guard; regression verifies the mocked worker is awaited and test singleton state is isolated.

## benchmark/README.md

- New sustained runner and memory methodology were absent; prior measurements could be read as final universal results. Added bounded sampling, timeouts, RSS scope and dated engine-specific evidence.

## docs/quality/local-release.md

- Guide required fresh environments per wheel although the script reinstalls into per-interpreter environments with external-origin checks. Corrected actual workflow, first-interpreter soaks and preparation-versus-publication state.

## docs/quality/continuous-improvement.md

- Process implied hosted jobs were the only release gate despite the authorized local route. Added equivalent local validation and actual publication/evidence boundaries.

## docs/quality/documentation.md

No drift detected.

## docs/audits/1.4.0/AUDITORIA.md

- Original pre-implementation snapshot lacked a prominent later-status boundary. Added a link to current published evidence without changing original findings.

## docs/audits/1.4.0/IMPLEMENTACION.md

- An earlier uncommitted/unpublished implementation snapshot could be mistaken for current release state. Added historical scope and current-publication links; original counts remain intact.

## docs/audits/1.4.0/CONTINUOUS_IMPROVEMENT.md

- Earlier 772/142 results and pending publication were not clearly separated from later release results. Added historical/current-status links without rewriting evidence.

## docs/audits/1.4.0/LOCAL_RELEASE.md

- Validation alone was not proof of upload. Linked the verified PyPI receipt, exact remote hashes and downloaded-wheel contract results.

