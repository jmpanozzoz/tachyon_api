"""Start isolated API/worker processes against explicit disposable services.

Does not provision services or truncate data. Creates only synthetic reference
accounts/jobs. Requires TEST_DATABASE_URL ending in _test and TEST_REDIS_URL.
"""
import argparse
import hashlib
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


async def ready(url, process):
    deadline = monotonic() + 15
    async with httpx.AsyncClient() as client:
        while monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("API process exited during startup; inspect private local log")
            try:
                if (await client.get(url + "/health/ready", timeout=1)).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(.1)
    raise TimeoutError("API startup timeout")


async def exercise(args, processes, logs):
    env = {**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"],
           "REDIS_URL": os.environ["TEST_REDIS_URL"], "ENVIRONMENT": "test", "DEBUG": "false",
           "SECRET_KEY": secrets.token_urlsafe(32), "PROVIDER_RESULT": "passed",
           "SOURCE_REVISION": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    counter = 0
    def spawn(module, *arguments):
        nonlocal counter
        log = (args.output / f"process-{counter}.log").open("w")
        logs.append(log)
        counter += 1
        process = subprocess.Popen([sys.executable, "-m", module, *arguments], cwd=ROOT,
                                   env=env, stdout=log, stderr=subprocess.STDOUT)
        processes.append(process)
        return process
    def api(port):
        return spawn("uvicorn", "example.app:app", "--host", "127.0.0.1", "--port", str(port),
                     "--no-access-log", "--timeout-graceful-shutdown", "5", "--ws-max-size", "4096")
    async def stop(process):
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            await asyncio.to_thread(process.wait, 10)
    ports = (free_port(), free_port())
    urls = [f"http://127.0.0.1:{port}" for port in ports]
    apis = [api(port) for port in ports]
    await asyncio.gather(*(ready(url, process) for url, process in zip(urls, apis)))
    worker = spawn("example.worker")
    result = {"started": datetime.now(timezone.utc).isoformat(), "source_revision": env["SOURCE_REVISION"],
              "source_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)),
              "source_fingerprints": {name: fingerprint(ROOT / name) for name in ("tachyon_api", "example")},
              "scope": "This host, two API processes, one job worker, real TCP/WebSocket/PostgreSQL/Redis. No Linux/container/multi-hour claim.", "checks": []}
    async with httpx.AsyncClient(base_url=urls[0], timeout=10) as first, httpx.AsyncClient(base_url=urls[1], timeout=10) as second:
        email, password = f"network-{uuid4().hex}@example.com", secrets.token_urlsafe(24)
        response = await first.post("/auth/register", json={"email": email, "password": password, "full_name": "Synthetic Network"})
        response.raise_for_status()
        login = await second.post("/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        customer = await second.post("/customers/", headers=headers, json={"first_name": "Synthetic", "last_name": "Network", "email": email})
        customer.raise_for_status()
        customer_id = customer.json()["customer_id"]
        assert (await first.get("/customers/" + customer_id, headers=headers)).status_code == 200
        result["checks"].append("identity_and_persistence_shared_between_api_processes")
        ticket = await second.post(f"/customers/{customer_id}/notification-ticket", headers=headers)
        ticket.raise_for_status()
        endpoint = f"ws://127.0.0.1:{ports[0]}/ws/notifications/{customer_id}?ticket={ticket.json()['ticket']}"
        async with websockets.connect(endpoint, origin="http://localhost:3000") as ws:
            assert json.loads(await asyncio.wait_for(ws.recv(), 5))["type"] == "connected"
            key = uuid4().hex
            started = await second.post("/verification/start", headers={**headers, "Idempotency-Key": key}, json={"customer_id": customer_id})
            started.raise_for_status()
            event = json.loads(await asyncio.wait_for(ws.recv(), 15))
            assert event["verification_id"] == started.json()["verification_id"] and event["status"] == "verified"
            result["checks"].append("worker_event_delivered_across_api_processes_via_redis")
        await stop(worker)
        restarted_key = uuid4().hex
        pending = await second.post("/verification/start", headers={**headers, "Idempotency-Key": restarted_key}, json={"customer_id": customer_id})
        pending.raise_for_status()
        verification_id = pending.json()["verification_id"]
        # Stop the HTTP process that accepted the write. Its memory cannot retain the job.
        await stop(apis[1])
        replacement = api(ports[1])
        await ready(urls[1], replacement)
        worker = spawn("example.worker")
        deadline = monotonic() + 15
        status = None
        while monotonic() < deadline:
            response = await first.get("/verification/" + verification_id, headers=headers)
            response.raise_for_status()
            status = response.json()["status"]
            if status == "verified":
                break
            await asyncio.sleep(.1)
        assert status == "verified"
        repeated = await second.post("/verification/start", headers={**headers, "Idempotency-Key": restarted_key}, json={"customer_id": customer_id})
        assert repeated.json()["verification_id"] == verification_id
        result["checks"].append("job_and_idempotency_survive_api_and_worker_restart")
    if args.duration:
        sys.path.insert(0, str(ROOT))
        from benchmark.run_reference_workload import run
        from importlib.metadata import version
        from types import SimpleNamespace
        workload = await run(SimpleNamespace(url=urls[0], expected_version=version("tachyon-api"),
            duration=args.duration, concurrency=4, samples=5000, expect_completion=True, completion_timeout=60))
        (args.output / "business-load.json").write_text(json.dumps(workload, indent=2) + "\n")
        assert not workload["errors"], workload["errors"]
        result["checks"].append("validated_business_load_zero_unexpected_errors")
    result["passed"] = True
    result["finished"] = datetime.now(timezone.utc).isoformat()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New private local evidence directory")
    parser.add_argument("--duration", type=float, default=10, help="Optional timed business load seconds; zero disables")
    args = parser.parse_args()
    if args.output.exists() or not 0 <= args.duration < float("inf"):
        parser.error("Use a new output directory and a finite nonnegative duration")
    if not urlsplit(os.getenv("TEST_DATABASE_URL", "")).path.endswith("_test") or not os.getenv("TEST_REDIS_URL"):
        parser.error("Set disposable TEST_DATABASE_URL ending in _test and TEST_REDIS_URL")
    args.output.mkdir(parents=True, mode=0o700)
    processes, logs = [], []
    try:
        report = asyncio.run(exercise(args, processes, logs))
        (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(5)
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
