# 1.4.3 simplification concepts brief

Author: Juan Manuel Panozzo Zenere.

Date: 2026-11-06. Target: `docs/quality/1.4.3-simplification.md`. Baseline: `f26f6060e7567260763e20cf09f7537d7f56af40`.

The user approved the anchored hypothesis and authorized implementing the whole plan. This brief translates its optional investigations into bounded implementation decisions; no further approval gate is introduced. Review is read-only and does not itself establish passing runtime behavior.

## Overview

Keep the public Python API, serializer choices, Starlette integration, default dependencies and server compatibility. Remove demonstrated duplicate state and unreachable work, fix middleware/docs consistency, and keep evidence reproducible. File/line reduction is a maintenance benefit; performance claims require comparable candidate measurements.

## Goals vs. non-goals

Goals: one middleware registration policy, deterministic docs publication, fewer
duplicated body/response controls, safe removal of redundant DI work, and
reproducible supported environments. Non-goals: replacing the router, adding a
native engine, changing default dependencies, removing public serializers or
rewriting CORS to mimic a dependency under new compatibility layers.

## Reviewer execution

All seven bundled lenses completed in fresh conversation contexts using `fork_turns: "none"`. Four total agent slots left two simultaneous reviewers alongside root and synthesizer, so dispatch proceeded in four waves. Host instruction-file exclusion is unverified; conversation-history isolation was explicitly requested. Each completion was verified from its actual final report, including persona/target/relevant source read evidence. Every reviewer completed on its first attempt; no failed reviewers or retries. Later reviewers explicitly distinguished the anchored baseline from root's concurrently evolving candidate. No reviewer edited runtime/tests or executed verification.

| Reviewer | Status | Attempts |
| --- | --- | --- |
| design_critic | completed | 1 |
| codebase_details | completed | 1 |
| zoom_out | completed | 1 |
| comprehension | completed | 1 |
| implementation_readiness | completed | 1 |
| structural | completed | 1 |
| inventive_catalyst | completed | 1 |

`brainstorm-reviewer-status.json` retains machine-readable status. The review found nine deduplicated Major implementation risks and one Nit boundary finding. Conditional blockers (lost app identity or unsafe DI caching) are avoided by the bounded choices below; completion does not certify the candidate implementation.

## Implementation decisions

| Item | Smallest safe choice | Evidence needed |
| --- | --- | --- |
| S01 | One lazy user chain around protocol dispatch; preserve HTTP first-registration-first order across protocols. Preserve late additions through explicit generation invalidation. Retain Starlette non-HTTP error/lifecycle machinery and explicitly define any app-identity correction. | Order, constructor counts, per-generation state, identity before/after delegation and inside endpoints/lifespan, startup/shutdown state, late addition, failed constructor retry, mounts, exceptions. |
| S02 | Keep first-scope preparation without requiring lifespan. Preflight canonical GET docs paths including pairwise conflicts/fixed `/swagger`; build every handler before committing trie/registry; mark done last. Protect installed docs routes from later GET overwrite. Bind pre-serve config/generator consistently and capture installed URLs. | Both collision registration orderings; docs-to-docs collisions; malformed paths; failure preserves state and retry; config replacement/in-place mutation before serving; post-setup mutation policy; request-owned root-path/external schema URLs. |
| S03 | Delete only proven unused metadata/method/plumbing; preserve used ClassFactory resolver, active lookup and public exports. | Existing compiler/DI contracts and repository consumers. |
| S04 | Remove unreachable validation catch/helper and unused import; retain existing DecodeError payload. | Malformed JSON and well-formed wrong-type JSON separately. |
| S05 | Share byte initialization/send mechanics while preserving sibling public response relationships and constructor signatures. Keep JSON encoding timing. | Both serializers; instance/subclass behavior; header mutation/copying; HEAD and bodyless statuses; backgrounds; existing response cleanup boundary; comparable microbenchmark. |
| S06 | Make current per-request bounded receive authoritative for framework-owned body access. Remove JSON-only checker after proving access convergence; document mutable limit correction. | Zero receive on oversized declared body; cumulative chunks; exact/zero/changed limits; JSON, direct/dependency Request, forms/files; 422 body; HTTP/1 retirement vs HTTP/2 headers; cleanup/cancellation. |
| S07 | Defer graph caching and revisioned registries. Consider only measured removal of immediate duplicate registered-class preparation where class resolution still validates before cache access and after construction. | In-place/replaced overrides; warm singletons; awaited/threaded mutation; lock waits; captured/root graph context; cycle detection; graph visits and actual workload costs. |
| S08 | Evaluate matrix, then defer delegation if preserving behavior recreates custom implementation. Preserve import/defaults and current behavior in this patch. | Origins, methods/headers/defaults/wildcards, preflight status/body/fallthrough, credentials/cookies, Vary/existing headers, errors, no-origin and non-HTTP pass-through. |
| S09 | Remove fake optional cache import only; retain invalid-config warning/proceed and decoration-time global config capture. | Existing cache contracts. |
| S10 | Early actionable Python support guard in quality tooling; document one supported development setup and label dependency resolution evidence honestly. | Supported vs unsupported interpreter behavior; current/locked/minimum versions distinguished; full suite and artifact checks as available. |
| S11 | Remove only collaborators naturally made redundant by accepted work; defer broad flattening. | Existing import/behavior contracts; no new generic abstraction. |
| S12 | Preserve packaging backend, mandatory dependencies, compatibility extras/facades, and historical evidence; add release evidence index. | Existing wheel/sdist/origin/hash checks and explicit platform limitations. |

## Analysis and alternatives weighed

- Middleware construction once per app conflicts with existing late additions. Preserve late registration and promise once per chain generation; an active lifespan can retain its previous generation. Do not silently add a startup freeze.
- Keeping Starlette as non-HTTP application entry preserves its previous `scope["app"]` identity; calling its built stack directly preserves Tachyon identity consistently. Either is possible, but the chosen correction must be explicit and tested. Bypassing Starlette's exception/lifespan stack is not justified.
- Shared response inheritance reduces code, but public subclass relationships are observable. Prefer a private common base or small shared initializer/sender that keeps the two public classes siblings.
- Docs config fields may change before serving, while registered paths must remain stable afterward. The candidate chooses a clear error for replacing the config object rather than rebinding all existing schema/renderers. Document constructor configuration and pre-serving field edits as supported, config-object replacement as rejected, and capture installed route URLs. A remote schema URL may be used for HTML links without installing a nonsensical local remote-URL route; record that explicit correction.
- S07/S08 are investigations, not mandatory rewrites. A complete plan can conclude that graph caching/CORS delegation is deferred when compatibility machinery would be larger than the existing code.

## Acceptance limits

Run affected regressions and defect reproducers, then the complete package/example suite. Keep baseline/candidate interpreter, resolved dependencies, workload and driver comparable; preserve raw outputs. ASGI batch costs do not establish network p95/p99, production capacity, endurance, or cross-platform compatibility. No numeric performance budget is supplied, so describe measurements rather than asserting unapproved thresholds. Record unavailable interpreter/platform/artifact verification honestly.

`brainstorm-findings.md` contains deduplicated implementation risks. Reviewer completion does not mean runtime tests passed.
