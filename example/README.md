# Synthetic KYC reference application

This development reference extends the existing demo. It requires the matching
**1.5.0.dev0 candidate**, not published Tachyon 1.4.3. It uses PostgreSQL instead
of global dictionaries and a deterministic synthetic provider, never real KYC.
Use synthetic data. Linux endurance, container execution and real pilots remain
separate acceptance gates; see the [implementation plan](../docs/quality/production-readiness.md).

## What it exercises

- Factory-created applications, lifespan engines/Redis clients, request-scoped
  services and generator dependencies with session cleanup.
- Argon2id hashing in a bounded thread pool; JWT issuer/audience/required claims;
  database-backed active users/roles; persistent account/client login limits.
- Customer ownership and admin-only recent/export operations, including cache hits.
- Verification + durable job committed atomically, idempotency keys, leased jobs,
  bounded retries, stale-worker fencing and post-commit notification events.
- Short-lived single-use WebSocket tickets with origin and ownership checks;
  Redis notifications across API processes and HTTP reconciliation after loss.
- Cache TTL/invalidation/fallback; bounded synthetic uploads that are not stored;
  bounded streaming export with the read transaction released before streaming.
- Liveness/readiness, correlation headers, sanitized logs and per-process metrics.
- Alembic migrations and separate worker resources. BackgroundTasks is still a
  framework feature, but is not used for durable verification processing.

## Local installation

From the repository root, create an environment, install the development checkout
or its validated wheel, then the example dependencies:

```sh
python -m pip install -e . -r example/requirements.txt
cp example/.env.example example/.env
```

The application reads environment variables; outside Compose, export them
explicitly. It does not automatically read `example/.env`. Set DATABASE_URL using
`postgresql+asyncpg://`, REDIS_URL and a stable random SECRET_KEY. Generate separate
secrets with `python -c 'import secrets; print(secrets.token_urlsafe(32))'`.
Development/test can generate an ephemeral signing key, but two HTTP workers
require the same explicit key. Production rejects missing/placeholder keys,
debug mode and the local-only DB placeholder. Pools have finite limits/timeouts.

```sh
python -m alembic -c example/alembic.ini upgrade head
uvicorn example.app:app --no-access-log --log-config example/logging.json --ws-max-size 4096
# In a separate terminal with the same environment:
python -m example.worker
```

Migrations are an explicit deployment step; HTTP/worker startup never creates
schema. No accounts are seeded automatically. Register a synthetic account via
POST /auth/register with email, password (10–128 characters) and full_name. For
an explicit development/test administrator, run:

```sh
python -m example.seed --email admin@example.com --admin
```

The password is prompted, not placed in the command line. Seed refuses production.
The provider result defaults to passed; PROVIDER_RESULT=failed or timeout enables
deterministic rejection/retry scenarios. These are simulations, not identity checks.

## Container deployment

Docker and Compose are required. Copy the env example and set separate random
SECRET_KEY and POSTGRES_PASSWORD values. From the repository root:

```sh
docker compose --env-file example/.env -f example/compose.yaml up --build
```

This builds the candidate wheel, runs a single migration job, starts two HTTP
workers and a separate job worker. PostgreSQL/Redis ports are not published; API
binds to loopback by default. Images are pinned by registry digest; their Linux
build/start validation remains pending until executed on the selected server.
Resource limits are initial test budgets, not sizing guidance. Compose reads the
env file explicitly. Keep its credentials and resolved config out of evidence.
Do not use a destructive volume reset against data you need.

## API flow

1. Register, then POST /auth/login; use its access_token as a Bearer header.
2. POST /customers/ and retain customer_id. GET /customers/me or /customers/{id}.
3. POST /verification/start with customer_id, verification_type (standard/enhanced)
   and a stable Idempotency-Key header. Reusing a key for different input is 409.
4. GET /verification/{id} for authoritative status. Jobs can complete without a
   connected HTTP client. The worker uses its own sessions and no request objects.
5. POST /customers/{id}/notification-ticket with authentication. Connect to
   /ws/notifications/{id}?ticket=... within 30 seconds with an allowed Origin.
   Tickets are consumed once before acceptance. Active identity/ownership is checked
   every 10 seconds; connections expire after five minutes and need a new ticket.
   The supplied logging config redacts tickets in Uvicorn WebSocket logs;
   --no-access-log alone does not suppress those messages. Sanitize proxy logs too.
6. WebSocket messages include connected, pong and verification_status. Notifications
   may be lost or duplicated; reconcile state over HTTP on every reconnect.
7. Optional POST /verification/{id}/document-check accepts a synthetic multipart
   document up to 256 KiB and returns its size/hash without storing it. The entire
   request is also limited to 1 MiB. This is not document storage or malware scanning.
8. Administrators can GET /customers/recent?limit=5, /customers/export (max 100
   NDJSON records) and /metrics. Metrics HTTP counters are per process; queue state
   is shared in PostgreSQL. Public /health/live and /health/ready have distinct roles.

Cache hits still check current user and ownership in PostgreSQL. Cache invalidation
and notification publication occur after durable completion and retry via the
outbox. Briefly stale cached status is bounded by TTL if invalidation is delayed;
GET /verification/{id} is authoritative. Redis Pub/Sub is not a durable event log.

## Tests and evidence

Provide **disposable** TEST_DATABASE_URL ending in `_test` and TEST_REDIS_URL.
Tests migrate and truncate the test DB and clear only reference:* Redis keys.
Run serially. Without TEST_DATABASE_URL integration tests skip explicitly; that
is not evidence of DB/Redis correctness.

```sh
python -m pytest example/tests/ -q
python -m pytest example/tests/ --cov=example --cov-config=example/.coveragerc
```

Tests cover real PostgreSQL/Redis behavior, HTTP auth/ownership, async-client
lifespan, job idempotency/leases/retries and authenticated notifications. Raw TCP,
two-worker behavior, service outages, restart recovery and long duration load
have additional gates. See the [Linux runbook](../docs/quality/linux-validation.md),
[operations runbook](../docs/quality/operations-runbook.md) and
[pilot template](../docs/adoption/pilot-template.md). Do not infer complete endpoint
coverage, absence of leaks or production readiness from a passing suite.

## CLI relationship

`tachyon new sample --profile postgres` creates a smaller persistent starter,
not a second copy of KYC. Its session template is checked against this reference.
`tachyon doctor` is read-only and offline by default; --app imports user code,
--connect explicitly checks configured services. The existing generation commands
retain their documented in-memory repositories; they are not automatically
rewritten into SQLAlchemy modules. See [the CLI guide](../docs/12-cli.md).
