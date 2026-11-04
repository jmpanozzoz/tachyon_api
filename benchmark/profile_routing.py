"""Route-count scaling of the actual Python matcher; not HTTP throughput."""
import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys
import time
import tracemalloc

from tachyon_api.routing.trie import RadixTrie
import tachyon_api.routing.trie as router_module


def build(count):
    trie = RadixTrie()
    handler = object()
    for index in range(count - 2):
        path = f"/static/{index}" if index % 2 == 0 else f"/api/r{index}/{{item}}/detail"
        trie.add(path, "GET", handler)
    trie.add("/backtrack/static/end", "GET", handler)
    trie.add("/backtrack/{value}/tail", "GET", handler)
    return trie, handler


def corpus(count, size=256):
    rng = random.Random(142)
    evens = list(range(0, count - 2, 2))
    odds = list(range(1, count - 2, 2))
    cases = {name: [] for name in ("static_hit", "dynamic_hit", "root_miss", "near_miss", "method_405", "backtrack")}
    for _ in range(size):
        even, odd = rng.choice(evens), rng.choice(odds)
        cases["static_hit"].append((f"/static/{even}", "GET", 2, {}))
        cases["dynamic_hit"].append((f"/api/r{odd}/42/detail", "GET", 2, {"item": "42"}))
        cases["root_miss"].append((f"/missing/{odd}", "GET", 0, {}))
        cases["near_miss"].append((f"/api/r{odd}/42/missing", "GET", 0, {}))
        cases["method_405"].append((f"/static/{even}", "DELETE", 1, {}))
        cases["backtrack"].append(("/backtrack/static/tail", "GET", 2, {"value": "static"}))
    return cases


def overlapping(count):
    depth = int(math.log2(count))
    trie = RadixTrie()
    handler = object()
    for mask in range(2 ** depth):
        segments = ["fixed" if mask & (1 << index) else f"{{p{index}}}" for index in range(depth)]
        trie.add("/overlap/" + "/".join(segments) + "/end", "GET", handler)
    for index in range(count - 2 ** depth):
        trie.add(f"/filler/{index}", "GET", handler)
    return trie, "/overlap/" + "/".join(["fixed"] * depth) + "/missing"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", type=int, nargs="+", default=[10, 100, 1000, 10000])
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--batches", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.counts) < 10 or min(args.repeats, args.batches) < 1:
        parser.error("Use at least ten routes and positive repeats/batches")
    report = {"python": sys.version, "platform": platform.platform(), "measurements": [],
        "framework_version": importlib.metadata.version("tachyon-api"),
        "router_origin": router_module.__file__,
        "router_sha256": hashlib.sha256(Path(router_module.__file__).read_bytes()).hexdigest(),
        "methodology": "Single-threaded matcher microbenchmark, six prevalidated 256-entry deterministic corpora plus a bounded adversarial overlapping miss. GC remains enabled. Timed calls are not revalidated. Includes iteration/unpacking overhead, excludes ASGI/server/validation/DI. Allocation bytes are tracemalloc Python allocations, not RSS. Not production capacity or Rust speed predictions."}
    for count in args.counts:
        gc.collect()
        tracemalloc.start()
        start = time.perf_counter_ns()
        trie, handler = build(count)
        registration_ns = time.perf_counter_ns() - start
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        for name, inputs in corpus(count).items():
            for path, method, status, params in inputs:
                result = trie.match(path, method)
                assert result[0] == status and result[2] == params, (name, result)
                assert result[1] is handler if status == 2 else result[1] is None
                assert result[3] == ("GET" if status == 1 else None)
            samples = []
            for _ in range(args.repeats):
                start = time.perf_counter_ns()
                for _ in range(args.batches):
                    for path, method, _, _ in inputs:
                        trie.match(path, method)
                samples.append((time.perf_counter_ns() - start) / (args.batches * len(inputs)))
            report["measurements"].append({"routes": count, "scenario": name, "ns_per_match": samples,
                "median_ns": statistics.median(samples), "registration_ns_under_tracemalloc": registration_ns,
                "retained_python_bytes": retained, "peak_python_bytes": peak})
        adversarial, path = overlapping(count)
        assert adversarial.match(path, "GET")[0] == 0
        samples = []
        for _ in range(args.repeats):
            start = time.perf_counter_ns()
            for _ in range(8):
                adversarial.match(path, "GET")
            samples.append((time.perf_counter_ns() - start) / 8)
        report["measurements"].append({"routes": count, "scenario": "overlapping_miss",
            "path": path, "ns_per_match": samples, "median_ns": statistics.median(samples),
            "calls_per_sample": 8, "note": "Many registered wildcard/static combinations, not a typical route tree"})
        print(f"{count} routes validated and measured", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
