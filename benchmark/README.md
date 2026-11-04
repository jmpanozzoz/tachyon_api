Run from the repository root with an environment containing Tachyon and the benchmark extra:

```sh
python -m benchmark.run_benchmark --requests 1000 --concurrency 4 --repeats 3 --output benchmark/results/local.json
# Or set PYTHON and invoke benchmark/run_benchmark.sh with the same arguments.
```

The [2026-11-04 assessment](../docs/quality/framework-review.md) retains a new
comparison with FastAPI 0.162.0, both Tachyon engines and shared server dependencies,
alongside the older dependency environment. Full latency samples are compressed
under [results/2026-11-04](results/2026-11-04/); versions, per-scenario medians,
ranges, p95/p99 and hashes are in the [summary](../docs/quality/evidence/2026-11-04/summary.json).
The extra in the audited snapshot restricted FastAPI to the 0.136 series; the
1.4.1 preparation updates it to >=0.162.0,<1.0. Reproducing dated results requires
installing their recorded versions in an isolated environment. These are local closed-loop results, with the same limits
described below; they do not establish a production capacity or global multiplier.

The runner defaults to Uvicorn/asyncio/h11. Select `--http httptools` to compare
its accelerated parser. For the optional Rust server, install `tachyon-api[granian]`
and pass `--server granian` (HTTP/1, asyncio, one runtime thread, no lifespan).
Keep framework, server and parser changes separate when interpreting results.
`tests/test_server_integration.py` runs real lifespan, shutdown, HTTP body limits,
uploads, streaming and WebSocket contracts when Granian/websockets are installed.
These POSIX signal shutdown tests are skipped on Windows; installed-wheel
contracts remain platform independent.

The runner launches separate standard Uvicorn servers, one worker each, using asyncio and h11. All Tachyon and FastAPI endpoints are async. Both create a Database through an async factory once per request, return dicts to response-model validation, and accept identical requests. The ASGI baseline parses the same valid inputs and constructs the same outputs, without framework validation or dependency machinery. It is a lower-bound reference; it does not implement the frameworks' error contracts.

Every warmup and measured request checks status, JSON content type, and exact decoded JSON. Incorrect warmup aborts the run. Measured errors are counted with their messages and cause a nonzero exit after saving results. The JSON artifact contains every latency sample, p50/p95/p99, successful throughput per scenario, repetitions, server command, interpreter, dependency versions, source revision and dirty status, and actual platform. Scenario and server order vary deterministically between repetitions. Connection setup and client validation are included in latency. Throughput is per scenario and is never summed.

This is a closed-loop loopback measurement with a Python threaded client on the same host. Client execution and CPU contention can limit throughput. Short runs establish correctness and repeatability; they do not establish production capacity or isolate framework overhead. Do not publish a framework multiplier from these artifacts. Sync/threadpool behavior is outside this async comparison; the profiling scripts measure components separately. `run_benchmark` does not sample memory; `run_soak` below records process RSS.

The retained `results/audit-1.4.0-python.json` records a controlled Python 3.13 run: two repetitions, three servers, eight scenarios, 200 requests per scenario, concurrency four, five warmups. All 9,600 measured responses passed validation with zero errors. The recorded source tree was under active audit, and the artifact identifies that dirty state. Rerun after final changes for release measurements.

The router's static priority is independent of HTTP method. A complete static route returns 405 if its method is unavailable, even when a wildcard route accepts that method. A static branch that ends without a registered terminal backtracks to wildcard alternatives. Wildcard parameter names belong to each terminal and method. Empty path segments, including repeated/trailing slashes, remain ignored; Unicode is indexed as characters in both engines.

`python -m benchmark.profile_breakdown --router-only --router-baseline /path/to/old_trie.py` compares standalone Python trie implementations. `results/audit-1.4.0-router-python.json` retains five batches of 100,000 lookups before and after the correctness fixes: approximately 234 to 337 ns for `/hello`, and 489 to 855 ns for `/users/42/profile`. This cost buys terminal-specific parameter names and fallback routing; compiled measurements must be run separately. The baseline file came from the recorded repository HEAD before this audit.

The historical `results/1.4.0-python.json` identifies version 1.4.0, the fallback engine, 48 measurements and 9,600 validated measured responses with zero errors. It was run after runtime fixes, with two repetitions and 200 requests per scenario. This remains a local closed-loop validation, not a production performance claim.


## Sustained local validation

Use the same environment and repository root for the source workload:

```sh
python -m benchmark.run_soak --duration 60 --concurrency 8 --samples 2000 --output benchmark/results/soak-local.json
```

This starts one Tachyon Uvicorn child with asyncio/h11 and persistent threaded
HTTP clients. Each client cycles the eight shared scenarios, including nested
bodies, response models and request-scoped callable dependencies. Every warmup
and measured response must match status, content type and exact JSON. Warmup
failure aborts; measured failures are counted by scenario and cause a nonzero
exit after writing the report. The measurement duration begins after warmup;
requests already in flight, RSS collection and shutdown can extend elapsed time.
Connections use a two-second socket timeout. The child is terminated and reaped,
with a kill fallback after ten seconds of shutdown.

The artifact records total/per-scenario counts, error examples, all-request
latency mean/max and sampled p50/p95/p99, engine/module origins, source version,
installed distribution versions and source revision/dirty state. Percentiles use
a uniform bounded priority reservoir, retaining at most `--samples` entries per
client and in the final artifact. RSS comes from `ps` in KiB converted to bytes,
is sampled roughly once per second, and is explicitly null when unavailable;
at most 7,200 RSS samples are retained. RSS is process resident memory, distinct
from the Python allocation measurements retained elsewhere.

The [local release record](../docs/audits/1.4.0/LOCAL_RELEASE.md) retains two
60-second runs on macOS ARM64/Python 3.10.22 with concurrency eight: 455,658
validated fallback responses and 481,519 native responses, both with zero errors.
[Fallback RSS samples](../docs/audits/1.4.0/local-release/soak-python.json) range
from 22,888,448 to 35,323,904 bytes;
[native RSS samples](../docs/audits/1.4.0/local-release/soak-native.json) range
from 32,915,456 to 38,043,648 bytes. These source-snapshot runs are separate from
the installed-wheel contracts. Their short duration does not prove absence of
leaks, multi-hour endurance, a production SLA or a global speed multiplier. Both
engines ran sequentially on the same host; historical raw benchmark artifacts
remain unchanged.
