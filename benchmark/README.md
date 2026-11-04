Run from the repository root with an environment containing Tachyon and the benchmark extra:

```sh
python -m benchmark.run_benchmark --requests 1000 --concurrency 4 --repeats 3 --output benchmark/results/local.json
# Or set PYTHON and invoke benchmark/run_benchmark.sh with the same arguments.
```

The runner launches separate standard Uvicorn servers, one worker each, using asyncio and h11. All Tachyon and FastAPI endpoints are async. Both create a Database through an async factory once per request, return dicts to response-model validation, and accept identical requests. The ASGI baseline parses the same valid inputs and constructs the same outputs, without framework validation or dependency machinery. It is a lower-bound reference; it does not implement the frameworks' error contracts.

Every warmup and measured request checks status, JSON content type, and exact decoded JSON. Incorrect warmup aborts the run. Measured errors are counted with their messages and cause a nonzero exit after saving results. The JSON artifact contains every latency sample, p50/p95/p99, successful throughput per scenario, repetitions, server command, interpreter, dependency versions, source revision and dirty status, and actual platform. Scenario and server order vary deterministically between repetitions. Connection setup and client validation are included in latency. Throughput is per scenario and is never summed.

This is a closed-loop loopback measurement with a Python threaded client on the same host. Client execution and CPU contention can limit throughput. Short runs establish correctness and repeatability; they do not establish production capacity or isolate framework overhead. Do not publish a framework multiplier from these artifacts. Sync/threadpool behavior is outside this async comparison; the profiling scripts measure components separately. Memory is not sampled by this network runner.

The retained `results/audit-1.4.0-python.json` records a controlled Python 3.13 run: two repetitions, three servers, eight scenarios, 200 requests per scenario, concurrency four, five warmups. All 9,600 measured responses passed validation with zero errors. The recorded source tree was under active audit, and the artifact identifies that dirty state. Rerun after final changes for release measurements.

The router's static priority is independent of HTTP method. A complete static route returns 405 if its method is unavailable, even when a wildcard route accepts that method. A static branch that ends without a registered terminal backtracks to wildcard alternatives. Wildcard parameter names belong to each terminal and method. Empty path segments, including repeated/trailing slashes, remain ignored; Unicode is indexed as characters in both engines.

`python -m benchmark.profile_breakdown --router-only --router-baseline /path/to/old_trie.py` compares standalone Python trie implementations. `results/audit-1.4.0-router-python.json` retains five batches of 100,000 lookups before and after the correctness fixes: approximately 234 to 337 ns for `/hello`, and 489 to 855 ns for `/users/42/profile`. This cost buys terminal-specific parameter names and fallback routing; compiled measurements must be run separately. The baseline file came from the recorded repository HEAD before this audit.

The final `results/1.4.0-python.json` identifies version 1.4.0, the fallback engine, 48 measurements and 9,600 validated measured responses with zero errors. It was run after runtime fixes, with two repetitions and 200 requests per scenario. This remains a local closed-loop validation, not a production performance claim.
