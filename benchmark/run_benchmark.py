"""Controlled loopback benchmark using only the standard library as load driver.

Run from repository root: python -m benchmark.run_benchmark --output benchmark/results.json
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import socket
import subprocess
import sys
import tempfile
import time

from benchmark.scenarios import SCENARIOS
from benchmark.server import server_command


def percentile(samples, fraction):
    return sorted(samples)[max(0, math.ceil(len(samples) * fraction) - 1)] if samples else None


def request(connection, scenario):
    _, method, path, payload, headers, expected = scenario
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {**headers, 'content-type': 'application/json'}
    connection.request(method, path, body=data, headers=headers)
    response = connection.getresponse()
    body = response.read()
    if response.status != 200:
        raise ValueError(f'HTTP {response.status}: {body[:200]!r}')
    if 'application/json' not in response.getheader('content-type', ''):
        raise ValueError('Expected JSON content-type')
    if json.loads(body) != expected:
        raise ValueError(f'Wrong response: {body[:200]!r}')


def worker(port, scenario, count):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    latencies, errors = [], Counter()
    for _ in range(count):
        started = time.perf_counter_ns()
        try:
            request(connection, scenario)
        except Exception as exc:
            errors[f'{type(exc).__name__}: {exc}'] += 1
            connection.close()
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        latencies.append((time.perf_counter_ns() - started) / 1e6)
    connection.close()
    return latencies, errors


def measure(port, scenario, requests, concurrency):
    counts = [requests // concurrency + (i < requests % concurrency) for i in range(concurrency)]
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        started = time.perf_counter()
        results = list(executor.map(lambda count: worker(port, scenario, count), counts))
        elapsed = time.perf_counter() - started
    latencies, errors = [], Counter()
    for samples, failures in results:
        latencies.extend(samples)
        errors.update(failures)
    failed = sum(errors.values())
    return {'requests': requests, 'successful': requests - failed, 'errors': dict(errors),
            'error_count': failed, 'seconds': elapsed, 'successful_requests_per_second': (requests - failed) / elapsed,
            'latency_ms': {'p50': percentile(latencies, .50), 'p95': percentile(latencies, .95), 'p99': percentile(latencies, .99)},
            'raw_latency_ms': latencies}


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def run_target(target, args, repeat):
    port = free_port()
    command = server_command(args.server, f'benchmark.app_{target}:app', port, args.http)
    with tempfile.TemporaryFile(mode='w+') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(f'{target} exited at startup:\n{log.read()}')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=.1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f'{target} did not start')
                    time.sleep(.05)
            # Fail immediately on incorrect warmup, before measuring anything.
            for scenario in SCENARIOS:
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
                try:
                    for _ in range(args.warmup):
                        request(connection, scenario)
                finally:
                    connection.close()
            rows = []
            scenarios = list(SCENARIOS)
            random.Random(args.seed + repeat).shuffle(scenarios)
            for scenario in scenarios:
                row = {'target': target, 'repeat': repeat, 'scenario': scenario[0], 'command': command,
                       **measure(port, scenario, args.requests, args.concurrency)}
                rows.append(row)
                print(f"{target:8} run={repeat} {scenario[0]:15} {row['successful_requests_per_second']:9.1f} req/s p99={row['latency_ms']['p99']:.3f}ms errors={row['error_count']}", flush=True)
            return rows
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', choices=('uvicorn', 'granian'), default='uvicorn')
    parser.add_argument('--http', choices=('h11', 'httptools'), default='h11', help='Uvicorn parser; Granian uses HTTP/1')
    parser.add_argument('--requests', type=int, default=1000, help='Requests per scenario per repetition')
    parser.add_argument('--concurrency', type=int, default=4)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--warmup', type=int, default=20)
    parser.add_argument('--seed', type=int, default=140)
    parser.add_argument('--output', type=Path, default=Path('benchmark/results.json'))
    args = parser.parse_args()
    if min(args.requests, args.concurrency, args.repeats, args.warmup) < 1:
        parser.error('counts must be positive')
    versions = {}
    for package in ('tachyon-api', 'fastapi', 'starlette', 'pydantic', 'uvicorn', 'granian', 'msgspec', 'orjson'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    import tachyon_api.routing.trie as trie
    report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'environment': {
        'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(), 'machine': platform.machine(),
        'processor': platform.processor(), 'cpu_count': os.cpu_count(), 'versions': versions, 'trie_module': trie.__file__,
        'git_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'git_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
    }, 'configuration': vars(args) | {'output': str(args.output)},
        'methodology': f'Async endpoints; per-request async DI factories; dict inputs to response models; equivalent valid JSON payloads. One worker, asyncio, server={args.server}, parser={args.http if args.server == "uvicorn" else "Granian HTTP/1"}, no lifespan/access logs. Closed-loop stdlib threaded client validates every status/body/content-type. Latencies include client validation and errors; connection establishment is included. ASGI baseline performs valid-input work without framework validation. Loopback throughput is client/machine dependent, not an isolated framework-overhead or production capacity measurement.', 'measurements': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for repeat in range(1, args.repeats + 1):
            targets = ['asgi', 'tachyon', 'fastapi']
            random.Random(args.seed + repeat).shuffle(targets)
            for target in targets:
                report['measurements'].extend(run_target(target, args, repeat))
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    if any(row['error_count'] for row in report['measurements']):
        raise SystemExit('Benchmark completed with errors; see output artifact.')


if __name__ == '__main__':
    main()
