# 1.4.3 bounded implementation review

Date: 2026-11-06. Scope: current runtime, test, quality/release and workflow changes implementing `docs/quality/1.4.3-simplification.md` and `concepts_brief.md`.

This was one code review with two fresh-context reviewers, not an iterative review loop. Both read their bundled persona, scope documents, actual candidate diff/new files, and relevant supporting source/tests. No reviewer edited files, compiled code or ran tests. Documentation/verification preparation continued concurrently in the root agent; findings refer to the inspected working tree.

## Actual reviewer status

| Reviewer | Context | Status | Attempts |
| --- | --- | --- | --- |
| codebase_details | `fork_turns: none` | completed; one actionable finding | 1 |
| implementation_readiness | `fork_turns: none` | completed; no actionable correctness defects found | 1 |

Both actual final reports were received before synthesis. No failure, retry, timeout or missing lens is represented as a clean review. Four total host slots allowed the two reviewers to run simultaneously beside root and synthesizer. Host instruction-file exclusion remains unverified.

## Actionable finding and resolution

### IR01 — Major: quality fingerprint omits the new shared test requirements

Location: `scripts/quality_cycle.py:41` and its directory-scan extension filter.

`scripts/test-requirements.txt` is now a shared input to CI and local release environment creation, but the explicit fingerprint inputs omit it, and recursive scanning only admits `.py`, `.pyx`, `.pxd`, `.yml` and `.md`. Changing dependency constraints can therefore leave `inputs_sha256` unchanged when source and already-installed versions stay the same, even though the environment-resolution instructions changed.

Smallest fix: include `ROOT / "scripts/test-requirements.txt"` in the explicit fingerprint input list. Candidate measurement/probe harnesses should use the same updated input definition when claiming matching source inputs.

Status at report creation: confirmed from current source; forwarded to the root for correction. This report does not claim the fix has shipped.

Root resolution: `scripts/test-requirements.txt` was added to the explicit quality
fingerprint input list before candidate validation. This is a source fix, not a
publication claim. Full-suite validation also caught overly strict rejection of
relative local schema URLs; the candidate now normalizes their registration path
and retains existing mounted-schema URL contracts. No new reviewer sign-off is
implied by these root-owned resolutions.

## Focused source conclusions

Neither reviewer found an actionable runtime defect in the requested focus paths:

- Docs canonical collision keys match trie nonempty-segment equivalence; framework handlers prepare before publication and completion is recorded last. Preparation failure leaves registry/trie unpublished and retry possible. External schema URLs are used as HTML links without creating malformed local routes.
- Middleware chain cache assignment occurs only after construction succeeds, allowing retry after failure. Late registration invalidates the shared generation; direct Starlette-stack delegation preserves Tachyon app identity. The documented generation policy permits an existing lifespan to retain its earlier chain.
- S07 registered-class delegation removes the immediate redundant preparation while retaining class-path validation before override/cache lookup and post-construction singleton validation.
- Shared response transport preserves public constructor parameter names and serializer entry behavior. Bounded receive remains the framework-owned body access authority.
- S10 shares requirements across workflow/release installation and rejects unsupported Python before runtime verification; the fingerprint omission identified above was corrected by root and independently confirmed in a follow-up source read.

## Read evidence and limits

Reviewed the current tracked diff plus new shared response base, shared requirements and simplification regression tests; relevant application facade/docs/installer/middleware/dispatch code; trie segmentation/matching; DI resolver/preparation/cache and graph/override tests; lifecycle, bounded scope/request/body access; response cleanup; quality/local release scripts; CI/wheel workflows; packaging declarations and supporting tests. The readiness reviewer also checked relevant packaging sources.

This establishes completed source review, not execution verification, cross-platform compatibility, passing artifact builds or performance acceptance. Root-owned test/probe/build evidence remains separate.

## Targeted follow-up: centralized body guard

Root identified a measured allocation regression in oversized declared JSON rejection and moved the single guard into `TachyonScope._check_body_limit`, called before request allocation by `body()` and before/after receive when needed. Root requested one fresh focused source review of these final guard changes. This follow-up concerns the guard only, not another broad review loop.

| Reviewer | Context | Actual status | Attempts |
| --- | --- | --- | --- |
| codebase_details, body-guard follow-up | `fork_turns: none` | completed; no correctness findings | 1 |

The actual final report was received before this appendix. No edits/tests were performed by the reviewer. The reviewer read its bundled persona, current scope/body extractor diff and deleted checker baseline, ManagedRequest, response processor, dispatcher, parameter access, upload ownership, related body/request/form/upload regression sources, and installed Starlette stream/multipart implementation.

Source-supported conclusions:

- Empty chunks leave cumulative bytes unchanged and safely repeat the same guard.
- Invalid Content-Length falls back to actual bytes; negative declarations cannot disable cumulative enforcement.
- Streamed overflow increments the counter before raising, so repeated reads reject before another underlying receive.
- Strict `>` comparison preserves exact-cap and zero-cap behavior.
- Declared oversize rejects before ManagedRequest creation in `body()`; repeated rejection remains safe and preserves the connection-retirement marker.
- Forms buffer through bounded receive before multipart parsing creates files. Returned uploads stay request-owned and unreturned parser handles close in `finally`.
- Producer finalization and request cleanup ownership remain intact; connection retirement copies outgoing response messages rather than mutating shared response headers.

No unresolved actionable correctness finding remains from this source review. Root's focused-test pass and forthcoming regenerated full matrix/artifact evidence are separate execution claims; this appendix does not certify those runs.
