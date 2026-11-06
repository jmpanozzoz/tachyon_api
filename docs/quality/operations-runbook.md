# Reference operations runbook

Operate only a synthetic test deployment until its acceptance checks pass. Keep
the previous application image/artifact and a tested backup before changing
schema or data. Record image digests, source revision, resolved dependencies,
configuration names and resource limits; never archive secret values.

## Start and observe

Run migrations once before HTTP/worker startup. `/health/live` indicates the
process responds; `/health/ready` checks DB and labels cache degradation. It does
not prove jobs are being processed. An administrator can read `/metrics`: HTTP
counts/buckets and pool counts are per process; durable queue state is shared.
Aggregate all worker processes externally. Inspect queue age in PostgreSQL in
addition to counts and alert on the business deadline, not just API availability.

HTTP logs contain status, elapsed time and a validated correlation ID. Use `--no-access-log --log-config example/logging.json`: Uvicorn emits
WebSocket URL messages through its error logger even with access logs disabled.
The supplied filter redacts the ticket parameter. Sanitize proxy logs as well. Do not log auth headers, passwords, documents or raw DB
exceptions/SQL parameters. Use a trusted proxy configuration before relying on
client addresses for rate limiting. Restrict metric access to operators.

## Failures

- **DB unavailable:** readiness returns 503. Check network, limits, pool usage and
  DB logs without exposing credentials. Liveness can remain up. Do not retry
  non-idempotent writes blindly; reuse the verification's idempotency key.
- **Redis unavailable:** reads fall back to DB and notifications disconnect/retry.
  Verification jobs remain in PostgreSQL. Unpublished events retry cache
  invalidation/publication after recovery. Pub/Sub messages can be lost or
  repeated; reconnect and fetch authoritative status by HTTP.
- **Worker exits:** restart the same artifact. Expired leases can be reclaimed;
  fencing tokens prevent a stale claim from completing the same job. A real
  external provider also needs its own idempotency contract. Do not promise
  exactly-once external effects from a database lease.
- **Queue grows:** compare pending age, attempts, failed jobs and worker resource
  limits. Diagnose a deterministic provider timeout separately from DB/Redis
  availability. A permanently failed job remains inspectable; do not silently
  delete/requeue every failed item.
- **Memory/FD growth:** compare equivalent post-warmup idle windows for all
  processes; inspect pool checkout, sockets and active streams. Distinguish
  bounded cache warmup and DB growth from leaked process resources.

## Shutdown, backup and rollback

Send SIGTERM to HTTP and worker processes, allow the configured grace period,
then verify pools/sockets are released and pending work can be reclaimed. An
interrupted worker can leave a lease until its deadline. Keep timeouts shorter
than shutdown grace. Forced termination is a distinct failure test.

Create an encrypted/access-restricted PostgreSQL backup using the deployed
version's supported tools. Restore into a separate disposable database and run
API/job consistency checks before relying on it. Keep credentials out of shell
history and command arguments; use the database tool's supported secret files or
environment mechanism. Never use the live database for restore drills.

Roll back the application to the prior artifact only with a schema compatible
with both versions. Prefer additive migrations and a staged expand/contract
sequence. The initial reference migration refuses destructive downgrade. A schema
downgrade is not a data-preserving rollback plan. If a migration loses data,
restoring a backup also loses subsequent writes and requires an explicit recovery
decision. Record the measured recovery time and data boundary.

## Required drill record

Record trigger, revision, start/end, expected/unexpected errors, recovery time,
lost/duplicate work, pool/FD recovery and follow-up actions for API restart, worker
restart, DB outage, Redis outage, timeout, restore and application rollback.
These procedures are pending execution on the user's Linux deployment; written
instructions do not establish that recovery has been demonstrated there.
