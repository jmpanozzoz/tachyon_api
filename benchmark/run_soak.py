"""Sustained validated loopback workload; local stability evidence, not an SLA.

Run: python -m benchmark.run_soak --duration 60 --concurrency 8 --output results.json
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
import heapq
import http.client
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import re
import socket
import subprocess
import sys
import tempfile
from threading import Event
import time

from benchmark.run_benchmark import free_port, percentile, request
from benchmark.scenarios import SCENARIOS


def worker(port, deadline, index, sample_limit, stop):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
    rng, samples, errors, counts, failures = random.Random(index), [], Counter(), Counter(), Counter()
    attempts, total_ms, maximum = 0, 0.0, 0.0
    try:
        while not stop.is_set() and time.monotonic() < deadline:
            scenario = SCENARIOS[(index + attempts) % len(SCENARIOS)]
            started = time.perf_counter_ns()
            try:
                request(connection, scenario)
            except Exception as exc:
                failures[scenario[0]] += 1
                message = f'{type(exc).__name__}: {exc}'[:300]
                errors[message if message in errors or len(errors) < 32 else 'Other errors'] += 1
                connection.close()
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
            elapsed = (time.perf_counter_ns() - started) / 1e6
            attempts += 1
            counts[scenario[0]] += 1
            total_ms += elapsed
            maximum = max(maximum, elapsed)
            # Keep the largest random priorities: merging worker reservoirs and
            # taking the largest again yields a uniform bounded global sample.
            sample = (rng.random(), elapsed)
            if len(samples) < sample_limit:
                heapq.heappush(samples, sample)
            elif sample[0] > samples[0][0]:
                heapq.heapreplace(samples, sample)
    finally:
        connection.close()
    return counts, failures, errors, samples, total_ms, maximum


def rss_bytes(pid):
    try:
        result = subprocess.check_output(['ps', '-o', 'rss=', '-p', str(pid)], text=True, timeout=2)
        return int(result.strip()) * 1024  # ps RSS is KiB on Linux and macOS.
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def environment():
    modules = ('routing.trie', 'processing.compiler', 'processing.dependencies._resolver', 'processing.response_processor')
    origins = {name: importlib.import_module('tachyon_api.' + name).__file__ for name in modules}
    compiled = [not origin.endswith('.py') for origin in origins.values()]
    versions = {}
    for package in ('tachyon-api', 'starlette', 'uvicorn', 'msgspec', 'orjson'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
            'engine': 'native' if all(compiled) else 'mixed' if any(compiled) else 'python',
            'module_origins': origins, 'installed_versions': versions,
            'source_version': re.search(r'^version = "([^"]+)"', Path('pyproject.toml').read_text(), re.MULTILINE).group(1),
            'git_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'git_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip())}


def run(args, report):
    port = free_port()
    command = [sys.executable, '-m', 'uvicorn', 'benchmark.app_tachyon:app', '--host', '127.0.0.1',
               '--port', str(port), '--workers', '1', '--loop', 'asyncio', '--http', 'h11',
               '--lifespan', 'off', '--no-access-log', '--log-level', 'warning']
    report['command'] = command
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        report['server_pid'] = process.pid
        try:
            startup_deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise RuntimeError('Server exited during startup')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=.1):
                        break
                except OSError:
                    if time.monotonic() >= startup_deadline:
                        raise RuntimeError('Server startup timed out')
                    time.sleep(.05)
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
            try:
                for scenario in SCENARIOS:
                    request(connection, scenario)
            finally:
                connection.close()
            started = time.monotonic()
            deadline = started + args.duration
            rss = [{'seconds': 0, 'bytes': rss_bytes(process.pid)}]
            report['server_rss_samples'] = rss
            stop = Event()
            with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                futures = [executor.submit(worker, port, deadline, index, args.samples, stop) for index in range(args.concurrency)]
                try:
                    while not all(future.done() for future in futures):
                        wait(futures, timeout=1)
                        if len(rss) < 7200:
                            rss.append({'seconds': time.monotonic() - started, 'bytes': rss_bytes(process.pid)})
                    rows = [future.result() for future in futures]
                finally:
                    stop.set()
            elapsed = time.monotonic() - started
            counts, failures, errors = Counter(), Counter(), Counter()
            for row in rows:
                counts.update(row[0])
                failures.update(row[1])
                errors.update(row[2])
            samples = [sample[1] for sample in heapq.nlargest(args.samples, (sample for row in rows for sample in row[3]))]
            total, failed = sum(counts.values()), sum(failures.values())
            report.update({'seconds': elapsed, 'requests': total, 'successful': total - failed,
                'error_count': failed, 'errors': dict(errors), 'scenario_requests': dict(counts),
                'scenario_errors': dict(failures), 'successful_requests_per_second': (total - failed) / elapsed,
                'latency_ms': {'mean': sum(row[4] for row in rows) / total if total else None,
                    'max': max(row[5] for row in rows),
                    **{f'p{p}': percentile(samples, p / 100) for p in (50, 95, 99)}},
                'latency_sample_count': len(samples), 'latency_sample_ms': samples,
                'rss_source': 'ps RSS KiB converted to bytes' if any(row['bytes'] is not None for row in rss) else None,
                'rss_samples_capped': len(rss) == 7200, 'server_exit_before_shutdown': process.poll()})
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            report['server_exit_after_shutdown'] = process.returncode
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 8000))
            report['server_log_tail'] = log.read().decode('utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=60, help='Sustained measured seconds, e.g. 30 or 60')
    parser.add_argument('--concurrency', type=int, default=8)
    parser.add_argument('--samples', type=int, default=2000, help='Maximum retained latency samples per worker and in report')
    parser.add_argument('--output', type=Path, default=Path('benchmark/results/soak.json'))
    args = parser.parse_args()
    if not 0 < args.duration < float('inf') or min(args.concurrency, args.samples) < 1:
        parser.error('duration, concurrency and samples must be finite and positive')
    report = {'started_utc': datetime.now(timezone.utc).isoformat(),
              'configuration': vars(args) | {'output': str(args.output)},
              'methodology': 'One worker, asyncio/h11, persistent closed-loop threaded clients cycling all shared scenarios. Every warmup/measured status, content-type and exact JSON validated. Latencies include validation and errors; percentiles use a bounded uniform priority reservoir, mean/max include all requests. RSS samples capped at 7200; unavailable RSS explicitly null. Local stability evidence; no production capacity or global SLA claim.'}
    try:
        report['environment'] = environment()
        run(args, report)
    except (Exception, KeyboardInterrupt) as exc:
        report['runner_error'] = f'{type(exc).__name__}: {exc}'
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report.get(key) for key in ('requests', 'successful', 'error_count', 'seconds', 'latency_ms', 'runner_error')}))
    if report.get('runner_error') or report.get('error_count') or not report.get('requests') or report.get('server_exit_before_shutdown') is not None:
        raise SystemExit('Soak failed; inspect the saved report.')


if __name__ == '__main__':
    main()
