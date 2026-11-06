# Published Tachyon 1.4.3 versus FastAPI

Measured 2026-11-06 on macOS ARM64 / CPython 3.13.18. Tachyon 1.4.3 was installed from public PyPI into an isolated environment; all installed Python bytes were compared with the validated published wheel. The driver ran outside the checkout so source could not shadow the installed package. FastAPI 0.162.0 uses Pydantic 2.14.3; both share Starlette 1.10.0 and Uvicorn 0.35.0. msgspec is 0.19.0 and orjson 3.13.0.

One Uvicorn worker, asyncio/h11, no access logs or lifespan, eight concurrent clients. Eight matched async workloads, same inputs and exact output checks, matching request-local dependency scope, and real response-model validation. Five repetitions, 2,000 measured requests per scenario/target/repetition, 100 warmups. Targets and scenarios are reordered per repetition. **240,000 measured responses, zero errors**, including the ASGI control.

| Scenario | Tachyon req/s | FastAPI req/s | Ratio | p99 Tachyon / FastAPI (ms) |
| --- | ---: | ---: | ---: | ---: |
| hello | 13,411 | 9,242 | 1.45× | 0.703 / 0.990 |
| path_query | 11,865 | 7,411 | 1.60× | 0.762 / 1.190 |
| body | 10,240 | 7,574 | 1.35× | 1.084 / 1.187 |
| nested_body | 10,084 | 7,521 | 1.34× | 1.122 / 1.188 |
| response_model | 12,835 | 8,703 | 1.47× | 0.749 / 1.035 |
| header | 12,785 | 8,340 | 1.53× | 0.736 / 1.097 |
| dependency | 11,303 | 7,899 | 1.43× | 0.905 / 1.166 |
| query | 11,675 | 7,139 | 1.64× | 0.789 / 1.359 |

These ratios are local scenario throughput observations, ranging from about 1.34× to 1.64×, not a framework-wide multiplier or production capacity forecast. Do not sum independent scenario rates. The ASGI control lacks framework validation and serves as a driver/transport reference, not an equivalent competitor. Pydantic v2 and msgspec both use native validation; this does not compare native validation against a pure-Python strawman.

Throughput numbers are medians of five repetitions. p50/p95/p99 in the [machine summary](fastapi-summary.json) are medians of per-repetition percentiles, not pooled percentiles. [Compressed raw measurements](fastapi-benchmark.json.gz) retain every measured latency and the full environment/configuration. Client and server share the host; CPU/thermal state is uncontrolled, and the Python client can limit rates. No database, external I/O, real authentication, invalid-input mix, multiworker load, sync workload, streaming or production traffic distribution is included in this comparison. The separate lifecycle and endurance audits cover other contracts but are not FastAPI comparisons.

The reproducible driver and matched apps are in the [release source](https://github.com/jmpanozzoz/tachyon_api/tree/v1.4.3/benchmark). The methodological requirement to compare validation/serialization workloads is also described in [FastAPI's benchmark guide](https://fastapi.tiangolo.com/benchmarks/).

## Codebase and production assessment

The owned runtime is 102 Python modules / 7,163 lines including comments and blanks, down 120 lines from 1.4.2. More useful than that count: middleware now has one registration/generation policy, docs cannot silently overwrite user routes, response transport is shared, body limits have one owner, and immediate duplicate DI graph validation is gone while safety checks remain. Publication validation has 933 source/example tests per supported interpreter and 229 installed-wheel contracts; public metadata is generated from version/hash-matched audits.

This is a credible base for controlled production pilots. It does not establish the operating history, ecosystem compatibility or support guarantees required to recommend immediate use for a critical enterprise service. Before that step, prioritize actual Linux deployment validation, multi-hour representative loads with database/cache dependencies, malformed/hostile input and disconnect testing, observable error/latency/resource budgets, and a documented security/support/deprecation policy. Starlette private hooks in request/form/routing integration need explicit dependency-compatibility checks. The documented OpenAPI/DI/model surface is narrower than FastAPI; migration is not drop-in.

Adoption should start with an isolated service, measurable workload, an owner, observability and a rollback path. Publish reproducible releases, migration examples and real pilot outcomes. The measured throughput advantage is useful evidence; reliability and the cost of maintaining an application remain the stronger production argument.
