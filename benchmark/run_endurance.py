"""Validated load/rest cycles on one server; resource evidence, not a capacity test."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
import hashlib
import heapq
import http.client
import json
from pathlib import Path
import subprocess
import time
from threading import Event

from benchmark.run_benchmark import free_port, request, percentile
from benchmark.run_soak import environment, worker, rss_bytes
from benchmark.scenarios import SCENARIOS
from benchmark.server import server_command


def open_descriptors(pid):
    proc = Path(f"/proc/{pid}/fd")
    try:
        if proc.is_dir():
            return len(list(proc.iterdir()))
        result = subprocess.check_output(["lsof", "-a", "-p", str(pid), "-Ff"], text=True, timeout=3)
        return sum(line.startswith("f") and line[1:].isdigit() for line in result.splitlines())
    except (OSError, subprocess.SubprocessError):
        return None


def run(args, report):
    port = free_port()
    command = server_command(args.server, "benchmark.app_tachyon:app", port, args.http)
    report["command"] = command
    report["phases"], report["resources"] = [], []
    counts, failures, errors = Counter(), Counter(), Counter()
    reservoir, total_ms, maximum = [], 0.0, 0.0
    started = time.monotonic()
    stop = Event()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_suffix(".server.log").open("w+") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        report["server_pid"] = process.pid
        def sample(phase):
            if len(report["resources"]) >= 7200:
                report["resource_samples_capped"] = True
                return
            report["resources"].append({"seconds": time.monotonic() - started, "phase": phase,
                "rss_bytes": rss_bytes(process.pid), "open_descriptors": open_descriptors(process.pid)})
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            try:
                deadline = time.monotonic() + 20
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Server exited during startup")
                    try:
                        for scenario in SCENARIOS:
                            request(connection, scenario)
                        break
                    except OSError:
                        connection.close()
                        if time.monotonic() > deadline:
                            raise RuntimeError("Server startup timed out")
                        time.sleep(.05)
            finally:
                connection.close()
            started = time.monotonic()
            active_seconds = 0.0
            sample("baseline")
            for cycle in range(args.cycles):
                phase = f"load-{cycle + 1}"
                phase_start = time.monotonic()
                deadline = phase_start + args.duration / args.cycles
                print(f"{phase} started", flush=True)
                with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                    futures = [executor.submit(worker, port, deadline, cycle * args.concurrency + i,
                                               args.samples, stop) for i in range(args.concurrency)]
                    last_progress = time.monotonic()
                    try:
                        while not all(f.done() for f in futures):
                            wait(futures, timeout=args.sample_interval)
                            if process.poll() is not None:
                                raise RuntimeError("Server exited during load")
                            sample(phase)
                            if time.monotonic() - last_progress >= 30:
                                print(f"{phase}: {time.monotonic() - phase_start:.0f}s", flush=True)
                                last_progress = time.monotonic()
                        rows = [f.result() for f in futures]
                    finally:
                        stop.set()
                stop.clear()
                elapsed = time.monotonic() - phase_start
                active_seconds += elapsed
                for row in rows:
                    counts.update(row[0])
                    failures.update(row[1])
                    errors.update(row[2])
                    reservoir = heapq.nlargest(args.samples, [*reservoir, *row[3]])
                    total_ms += row[4]
                    maximum = max(maximum, row[5])
                report["phases"].append({"phase": phase, "seconds": elapsed,
                    "requests": sum(sum(row[0].values()) for row in rows),
                    "errors": sum(sum(row[1].values()) for row in rows)})
                phase = f"idle-{cycle + 1}"
                print(f"{phase} started", flush=True)
                deadline = time.monotonic() + args.idle
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Server exited during idle")
                    time.sleep(min(args.sample_interval, max(0, deadline - time.monotonic())))
                    sample(phase)
                sample(phase + "-end")
            samples = [pair[1] for pair in reservoir]
            total, failed = sum(counts.values()), sum(failures.values())
            report.update({"seconds": time.monotonic() - started, "active_seconds": active_seconds,
                "requests": total, "successful": total - failed, "error_count": failed,
                "scenario_requests": dict(counts), "scenario_errors": dict(failures), "errors": dict(errors),
                "latency_ms": {"mean": total_ms / total if total else None, "max": maximum,
                    **{f"p{p}": percentile(samples, p / 100) for p in (50, 95, 99)}},
                "latency_sample_ms": samples})
            report["server_exit_before_shutdown"] = process.poll()
        finally:
            stop.set()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            report["server_exit_after_shutdown"] = process.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=1800, help="Total active load seconds across all cycles")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--idle", type=float, default=30, help="Idle seconds after each cycle")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--sample-interval", type=float, default=5)
    parser.add_argument("--server", choices=("uvicorn", "granian"), default="uvicorn")
    parser.add_argument("--http", choices=("h11", "httptools"), default="h11")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not all(0 < v < float("inf") for v in (args.duration, args.sample_interval)) or not 0 <= args.idle < float("inf") or min(args.cycles, args.concurrency, args.samples) < 1:
        parser.error("Durations/counts must be finite and positive; idle can be zero")
    if args.server == "granian" and args.http != "h11":
        parser.error("Use --http h11 with Granian; the server selects its own HTTP/1 stack")
    digest = hashlib.sha256()
    for path in sorted(Path("tachyon_api").rglob("*.py")):
        digest.update(str(path).encode() + b"\0" + path.read_bytes() + b"\0")
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "environment": environment(),
        "runtime_sha256": digest.hexdigest(), "configuration": vars(args) | {"output": str(args.output)},
        "methodology": "One persistent server with validating threaded clients. Total duration is active load; idle follows every cycle. Exact status/content-type/JSON validation. Resource samples describe the child, not client. Percentiles use a bounded uniform priority reservoir; mean/max use all requests. Host contention is uncontrolled. No capacity/SLA or leak-free guarantee."}
    try:
        run(args, report)
    except (Exception, KeyboardInterrupt) as exc:
        report["runner_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report.get(k) for k in ("requests", "error_count", "seconds", "runner_error")}))
    if report.get("runner_error") or report.get("error_count") or not report.get("requests") or report.get("server_exit_before_shutdown") is not None:
        raise SystemExit("Endurance failed; inspect the saved report")


if __name__ == "__main__":
    main()
