# Linux validation on the available server

Server access and inventory are pending from the owner. Do not infer a target
from local SSH configuration or connect to an unrelated host. The validation
script runs on the selected host; it does not SSH, provision services or change
firewall/host limits. Use an isolated directory, user, ports and resource budget
if the server shares services.

## Inventory first

```sh
python scripts/linux_validation.py --output /tmp/tachyon-linux-inventory
```

This records OS/kernel/architecture, CPU count, memory, disk and FD limits. Also
record existing services, assigned ports, available CPU/RAM/disk and whether an
external load generator is available. Inventory alone is not Linux test evidence.

## Installed and source contracts

Prepare explicit Python 3.10–3.13 interpreter paths, uv and disposable PostgreSQL
and Redis instances. Set `TEST_DATABASE_URL` to a database ending in `_test` and
`TEST_REDIS_URL` to an isolated Redis database. The reference tests truncate that
database and clear `reference:*` keys. Run them serially. Secrets stay outside git
and evidence archives.

```sh
python scripts/linux_validation.py --execute \
  --python /path/to/python3.10 --python /path/to/python3.11 \
  --python /path/to/python3.12 --python /path/to/python3.13 \
  --uv /path/to/uv --output /tmp/tachyon-linux-candidate
```

Use `--artifacts /path/to/validated-dist` to test the same wheel/sdist pair built
on another host. Keep their hashes and compare metadata/origins. Do not claim
another architecture or Windows from this server. Baseline 1.4.3 must be tested
from its immutable tag/artifacts using its own contracts, not the candidate's new
generator dependency tests.

## Reference deployment and load

Follow [the reference guide](../../example/README.md). Its Docker images are
pinned by registry manifest digest. Dockerfile/Compose still require an actual
Linux build/start check; a manifest lookup is not container execution evidence.
Use a separate synthetic database from the contract suite.

```sh
python -m benchmark.run_reference_workload \
  --url http://127.0.0.1:8000 --expected-version 1.5.0.dev0 \
  --duration 600 --concurrency 8 --expect-completion \
  --output /tmp/tachyon-reference-smoke.json
```

The driver creates synthetic users, customers and jobs. It validates payloads,
expected 422s and latency samples; no bearer tokens are written. Configure account
and client limits for the test without disabling them for unrelated services.
Start with 10 minutes, then 2 hours, 8 hours with idle intervals, and 24 hours
before an important pilot. Review each stage before escalating. Use a new output
path for each run. The client must not saturate unnoticed; use another machine
where possible and record co-location when not.

The framework `benchmark.run_endurance` load/rest probe remains a separate
transport/resource check. Collect API/worker/PostgreSQL/Redis CPU, RSS, FDs,
pool counts, queue age and event-loop lag externally as appropriate. The business
driver's combined percentiles include invalid-input traffic and are reservoir
estimates; they are not per-route exact percentiles or application capacity.

Follow [recovery drills](operations-runbook.md) and the
[acceptance budgets](production-readiness.md#p2-linux-y-operación-en-el-servidor-disponible).
Preserve raw measurements and actual gaps. Missing interpreters, Docker build
coverage, outage drills, long soaks and pilots stay pending until executed.
