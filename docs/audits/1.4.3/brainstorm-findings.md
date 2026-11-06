# 1.4.3 brainstorm findings

Target: `docs/quality/1.4.3-simplification.md` at baseline `f26f6060e7567260763e20cf09f7537d7f56af40`.

This is an implementation risk review, not a claim of released defects or completed implementation. Reviewer completion is recorded separately in `brainstorm-reviewer-status.json`. The root began authorized implementation during later reviews; reviewers explicitly distinguished historical baseline observations from the changing checkout.

## Deduplicated findings

### F01 — Major: middleware scope identity is a protocol contract

Sources: `tachyon_api/app/_asgi_entry.py`, `tachyon_api/app/__init__.py`, `tachyon_api/middlewares/core.py`, `tachyon_api/core/websocket.py`, `tachyon_api/processing/scope.py`.

The HTTP chain currently receives Tachyon in `scope["app"]`; Starlette's non-HTTP entry replaces it with Starlette. A common user chain must preserve HTTP identity because body limits read Tachyon configuration. Calling Starlette's built middleware stack directly can preserve Tachyon identity across protocols while retaining its error/lifecycle wrappers; that intentionally changes current WebSocket/lifespan identity and must be documented and tested before/after middleware delegation, inside endpoints/lifespan, and across mounts. Resolver binding must remain explicit.

### F02 — Major: middleware construction and late additions need a lifetime policy

Sources: `tachyon_api/app/_mw_stack.py`, `tachyon_api/app/__init__.py`, `tachyon_api/middlewares/core.py`.

Preserve HTTP first-registration-first order when unifying protocols. One chain per generation removes duplicate registrations and eager reconstruction. Preserve existing late registration with explicit invalidation unless a separately documented restriction is intended. Middleware spanning an active lifespan can remain in an older generation than subsequent requests; test/document that boundary and never claim one construction per app when invalidation is supported. Constructor failure must leave retry possible. Reviewers differed on freezing versus preserving late registration; preserving the existing API is the compatibility default.

### F03 — Major: docs setup requires a bounded transaction

Sources: `tachyon_api/app/_docs_routes.py`, `_route_installer.py`, `_registry.py`, `tachyon_api/routing/trie.py`.

Setting completion last alone does not repair partial installation. Preflight all canonical GET destinations, pairwise configured collisions, fixed `/swagger`, and existing user routes; compile/build all four handlers before mutating live state. Commit trie and registry consistently, with no schema side effects for hidden docs routes. Reject later user GET overwrites of installed framework routes. Keep ordinary user-route replacement policy separate and support first HTTP request without lifespan. Failure must preserve prior state and permit retry.

### F04 — Major: docs config and generator must bind together

Sources: `tachyon_api/app/_docs_routes.py`, `tachyon_api/openapi/_config.py`, `_generator.py`.

Config is mutable and replaceable, while the generator and renderers capture earlier configuration. Bind the selected pre-first-scope config consistently to generator/renderers before docs preparation. Capture installed route URLs; changes after installation must not silently redirect only HTML schema links. Rebuilding the generator must preserve ordinary registered routes and common schemas.

### F05 — Major: body-limit consolidation changes mutation behavior

Sources: `tachyon_api/processing/parameters.py`, `scope.py`, `_extractors/body.py`, `_extractors/body_limit.py`, `response_processor.py`; `tests/test_operational_cleanup.py`.

JSON's checker captures the construction-time limit while bounded receive reads the current per-request app limit. Choose the current per-request limit as the single authority and record the correction. Verify JSON, injected/dependency Request, forms/files all pass through bounded receive. Preserve zero-read declared-size rejection, cumulative chunk checks, exact/zero limits, 422 payload, rejection marker, HTTP/1 retirement, HTTP/2 header omission, upload cleanup and cancellation shielding.

### F06 — Major: DI plan caching risks lifetime regressions

Sources: `tachyon_api/processing/dependencies/_resolver.py`, `_sig_cache.py`; `tests/test_continuous_di.py`, `test_continuous_di_graph.py`.

Keep pre-cache and post-construction lifetime/override validation, including changes during awaited/threaded construction and lock waits. Dictionary identity is insufficient because overrides mutate in place and can be replaced. Defer graph caching/revisioned registries. A separate measured candidate may dispatch registered classes before duplicate callable preparation, retaining class-path validation and race checks.

### F07 — Major: CORS replacement changes observable behavior

Sources: `tachyon_api/middlewares/cors.py`, `tests/test_cors_middleware.py`, baseline probes.

Default methods, invalid preflight status/body, unsupported-origin fallthrough, wildcard method expansion, safelisted headers, cookie/credential origin echo, and Vary handling differ. Defer delegation when preserving these requires recreating the custom implementation. A future migration requires an explicit behavior matrix; observed status 200 alone does not establish an authorization bypass.

### F08 — Major: response sharing must preserve public type behavior

Sources: `tachyon_api/responses/_bytes_response.py`, `_json_response.py`, `tachyon_api/processing/response_processor.py`.

A small shared private JSONResponse base preserves sibling public class relationships better than making one public response inherit the other. Keep signatures, encoder timing, copied send headers, mutable instance headers, HEAD length/body behavior, informational/204/304 suppression, background execution and response/stream cleanup ownership. Measure any added constructor call before claiming a speedup.

### F09 — Major: verification must identify the actual supported environment

Sources: `scripts/quality_cycle.py`, `pyproject.toml`, `docs/audits/1.4.3/simplification-baseline.json`.

Reject unsupported interpreters before package verification or test collection. Record resolved versions/import origin; distinguish the recorded 3.13/Starlette 1.10.0 environment from lock/minimum/current resolutions. Preserve raw candidate evidence and baseline hashes. Existing ASGI timings include driver/validation and establish neither network capacity nor latency percentiles.

The original decode probe instruments the helper that S04 deletes; adapt candidate instrumentation without changing historical baseline artifacts. Development setup must include PyJWT needed by example collection, not just package development dependencies.

### F10 — Nit: keep deletions narrow

Remove only demonstrated unused fields, unreachable decode handling, and the fake optional cache import. Preserve ClassFactory's used resolver, public exports, existing invalid-cache logging, global decoration-time cache behavior, module compatibility where inexpensive, packaging/dependency defaults, empty `[fast]`, server facade, release checks and historical audits. Defer broad collaborator/backend/CLI restructuring.

## Reviewer provenance and disagreements

| Lens | Source-supported contribution | Qualification |
| --- | --- | --- |
| design_critic | Middleware lifetime/identity; docs atomicity and generator binding; mutable limits; DI post-construction validation. | Preferred freezing middleware after first scope; synthesis favors compatible generation invalidation. |
| codebase_details | Same cross-protocol/config hazards; private shared response base; preserve ordinary user duplicate-route policy separately. | Inspected source plus relevant installed Starlette entry and fetched current docs; no execution validation. |
| zoom_out | Bound S06 to framework-owned body access; prefer measured immediate DI class delegation over graph cache; avoid generalized registries. | Explicitly noted missing guessed config filename and did not claim reading actual config implementation. |
| comprehension | Clear reserved-path/interpreter errors; pre/post-setup config contract; preserve schema URL/root_path behavior; keep performance observational without budgets. | Focused source/test read, no exhaustive audit. |
| implementation_readiness | Preserve response keyword constructors; include example-test dependencies; test failure on third docs handler and retry. | Noted concurrent candidate changes; inherited bytes constructor actually retains `body`, so concern is a verification requirement, not confirmed signature regression. |
| structural | Candidate probes must survive removed helper; preserve empty-chunk/body-limit semantics and source lifetime ownership. | Marked identity loss/unsafe DI caching as conditional blockers; bounded chosen designs address these, not unconditional release blockers. |
| inventive_catalyst | Three contradictions: shared lifetime vs late additions, mutable config vs fixed routes, cached validation vs override safety. Confirmed candidate signatures match baseline (`body`, `content`). | Favored freezing registration; compatible generation policy retained. Baseline probes remain historical; candidate regressions must avoid deleted-helper/old-overwrite assumptions. |

## Completion and severity

All seven requested reviewers returned actual final reports after reading their bundled persona, target and relevant source/tests. Every reviewer completed on its first attempt; no failures, timeouts or retries were hidden. No reviewer edited runtime code/tests or executed verification. Four-slot host concurrency limited this review to two child reviewers at once, in four waves. Later reviewers observed root's concurrent implementation and identified that distinction.

The deduplicated set contains nine Major implementation risks and one Nit cleanup-boundary finding. Structural marked app-identity loss and unsafe DI cache shortcuts as conditional Blockers; these are addressed by explicit scope identity and retaining DI validation, rather than asserted as unconditional release blockers. This synthesis is design evidence, not a candidate release-readiness claim.
