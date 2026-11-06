"""Validate synthetic reference traffic over HTTP; never stores bearer tokens.

Run only against the synthetic test deployment. Creates synthetic accounts,
customers and verification jobs. An independent worker must consume the jobs.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import random
import statistics
import time
from uuid import uuid4

import httpx


async def run(args):
    latencies, errors, total, statuses = [], {}, 0, {}
    verification_writes = 0
    rng = random.Random(42)
    run_id = uuid4().hex
    async with httpx.AsyncClient(base_url=args.url, timeout=10, follow_redirects=False) as client:
        identity = (await client.get("/")).json()
        if identity.get("framework_version") != args.expected_version:
            raise ValueError("The running server does not match --expected-version")
        accounts = []
        for index in range(args.concurrency):
            email, password = f"load-{run_id}-{index}@example.com", uuid4().hex
            response = await client.post("/auth/register", json={"email": email, "password": password, "full_name": "Synthetic Load"})
            response.raise_for_status()
            login = await client.post("/auth/login", json={"email": email, "password": password})
            login.raise_for_status()
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            customer = await client.post("/customers/", headers=headers,
                json={"first_name": "Synthetic", "last_name": "Load", "email": email})
            customer.raise_for_status()
            accounts.append((headers, customer.json()["customer_id"], email, password, time.monotonic() + max(1, login.json()["expires_in"] - 60)))
        started = time.monotonic()
        deadline = started + args.duration
        async def worker(index, headers, customer_id, email, password, refresh_at):
            nonlocal total, verification_writes
            sequence, last_verification = 0, None
            while time.monotonic() < deadline:
                if time.monotonic() >= refresh_at:
                    login = await client.post("/auth/login", json={"email": email, "password": password})
                    login.raise_for_status()
                    headers["Authorization"] = "Bearer " + login.json()["access_token"]
                    refresh_at = time.monotonic() + max(1, login.json()["expires_in"] - 60)
                sequence += 1
                case = sequence % 10
                before = time.perf_counter()
                try:
                    if case == 0:
                        response = await client.post("/verification/start", headers={**headers, "Idempotency-Key": f"{run_id}-{index}-{sequence}"},
                            json={"customer_id": customer_id, "verification_type": "standard"})
                        response.raise_for_status()
                        value = response.json()
                        assert value["customer_id"] == customer_id and len(value["checks"]) == 3
                        last_verification = value["verification_id"]
                        verification_writes += 1
                        expected = 200
                    elif case == 1:
                        response = await client.post("/verification/start", headers=headers, json={"customer_id": customer_id})
                        expected = 422
                        assert response.status_code == expected
                    elif case == 2 and last_verification:
                        response = await client.get("/verification/" + last_verification, headers=headers)
                        expected = 200
                        assert response.json()["customer_id"] == customer_id
                    elif case == 3:
                        response = await client.get("/auth/me", headers=headers)
                        expected = 200
                        assert response.json()["role"] == "user"
                    elif case == 4:
                        response = await client.get("/health/ready")
                        expected = 200
                        assert response.json()["database"] == "up"
                    else:
                        response = await client.get("/customers/" + customer_id, headers=headers)
                        expected = 200
                        assert response.json()["customer_id"] == customer_id
                    assert response.status_code == expected
                    assert "application/json" in response.headers.get("content-type", "")
                    statuses[str(response.status_code)] = statuses.get(str(response.status_code), 0) + 1
                except Exception as exc:
                    name = type(exc).__name__
                    errors[name] = errors.get(name, 0) + 1
                elapsed = (time.perf_counter() - before) * 1000
                total += 1
                if len(latencies) < args.samples:
                    latencies.append(elapsed)
                else:
                    replacement = rng.randrange(total)
                    if replacement < args.samples:
                        latencies[replacement] = elapsed
            return last_verification
        last = await asyncio.gather(*(worker(i, *account) for i, account in enumerate(accounts)))
        elapsed = time.monotonic() - started
        completion = []
        if args.expect_completion:
            for account, verification_id in zip(accounts, last):
                if not verification_id:
                    continue
                until = time.monotonic() + args.completion_timeout
                status = None
                while time.monotonic() < until:
                    response = await client.get("/verification/" + verification_id, headers=account[0])
                    response.raise_for_status()
                    status = response.json()["status"]
                    if status in {"verified", "rejected", "failed", "expired"}:
                        break
                    await asyncio.sleep(.5)
                completion.append(status)
                if status != "verified":
                    errors["JobCompletion"] = errors.get("JobCompletion", 0) + 1
    ordered = sorted(latencies)
    def percentile(p):
        return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))] if ordered else None
    return {"recorded_at": datetime.now(timezone.utc).isoformat(), "server_identity": identity,
        "client_platform": platform.platform(), "concurrency": args.concurrency,
        "duration_seconds": elapsed, "requests": total, "run_id": run_id, "verification_writes": verification_writes, "errors": errors, "validated_statuses": statuses,
        "rate": total / elapsed, "sample_count": len(latencies),
        "latency_ms": {"sample_mean": statistics.mean(latencies) if latencies else None,
                       "p50": percentile(.50), "p95": percentile(.95), "p99": percentile(.99)},
        "completion": completion,
        "methodology": "Reservoir latency sample across all workloads, including failures and expected 422. Accounts/login/setup, token refresh and completion polling excluded from request counters/latency samples (refresh time remains in wall duration). Concurrency tasks share one client host. No capacity/SLA or multi-host claim. One synthetic verification write per ten requests; other cases read/auth/health or intentional invalid input. Latest job per worker optionally checked after load; this does not prove completion of all jobs.",
        "latency_reservoir_ms": latencies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--duration", type=float, default=600)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--expect-completion", action="store_true")
    parser.add_argument("--completion-timeout", type=float, default=300)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (0 < args.duration < float("inf") and 0 < args.completion_timeout < float("inf") and
            1 <= args.concurrency <= 32 and args.samples > 0):
        parser.error("Durations/counts must be finite and positive; concurrency is limited to 32")
    if args.output.exists():
        parser.error("Output already exists; preserve evidence")
    report = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("requests", "errors", "latency_ms")}))
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
