"""Interleave identical baseline/candidate benchmark commands on one interpreter.

ASGI results include driver/validation cost. Network percentiles summarize each
block separately; medians of block percentiles are not pooled percentiles.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
from types import SimpleNamespace


def network_worker(output, repeat):
    sys.path.insert(0, str(Path.cwd()))
    from benchmark.run_benchmark import run_target
    import tachyon_api
    root = Path(tachyon_api.__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    args = SimpleNamespace(server="uvicorn", http="h11", requests=1000, concurrency=8, warmup=100, seed=140)
    rows = run_target("tachyon", args, repeat)
    assert not any(row["error_count"] for row in rows)
    output.write_text(json.dumps({"runtime_root": str(root), "runtime_sha256": digest.hexdigest(),
        "versions": {name: importlib.metadata.version(name) for name in
                     ("starlette", "uvicorn", "msgspec", "orjson")},
        "configuration": vars(args), "measurements": rows}) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("asgi", "network"))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--blocks", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", type=int)
    args = parser.parse_args()
    if args.worker is not None:
        network_worker(args.output, args.worker)
        return
    if args.blocks < 1 or any(value is None for value in (args.baseline, args.candidate, args.python)):
        parser.error("supply baseline/candidate roots, interpreter and positive blocks")
    script = Path(__file__).resolve()
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "kind": args.kind,
              "python_executable": str(args.python), "driver_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
              "methodology": __doc__, "blocks": [], "summary": {}}
    with tempfile.TemporaryDirectory(prefix="tachyon143-comparison-") as temporary:
        for block in range(args.blocks):
            order = ("baseline", "candidate") if block % 2 == 0 else ("candidate", "baseline")
            for label in order:
                root = getattr(args, label).resolve()
                output = Path(temporary) / f"{block}-{label}.json"
                command = ([str(args.python), "-m", "benchmark.profile_hotpath", "--iterations", "5000", "--repeats", "3", "--output", str(output)]
                    if args.kind == "asgi" else [str(args.python), str(script), "network", "--worker", str(block), "--output", str(output)])
                result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                if result.returncode:
                    raise RuntimeError(result.stdout)
                data = json.loads(output.read_text())
                data.update(label=label, block=block, command=command,
                    source_version=re.search(r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(), re.M)[1])
                report["blocks"].append(data)
                print(f"{args.kind} block {block + 1}/{args.blocks}: {label}", flush=True)
    for label in ("baseline", "candidate"):
        blocks = [block for block in report["blocks"] if block["label"] == label]
        assert len({block["runtime_sha256"] for block in blocks}) == 1
        if args.kind == "asgi":
            report["summary"][label] = {name: statistics.median(block["medians_ns"][name] for block in blocks)
                                         for name in blocks[0]["medians_ns"]}
        else:
            rows = [row for block in blocks for row in block["measurements"]]
            report["summary"][label] = {name: {
                "requests": sum(row["requests"] for row in rows if row["scenario"] == name),
                "errors": sum(row["error_count"] for row in rows if row["scenario"] == name),
                "median_successful_rps": statistics.median(row["successful_requests_per_second"] for row in rows if row["scenario"] == name),
                "median_block_p95_ms": statistics.median(row["latency_ms"]["p95"] for row in rows if row["scenario"] == name),
                "median_block_p99_ms": statistics.median(row["latency_ms"]["p99"] for row in rows if row["scenario"] == name),
            } for name in {row["scenario"] for row in rows}}
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(report, indent=2) + "\n").encode()
    args.output.write_bytes(gzip.compress(payload, mtime=0) if args.output.suffix == ".gz" else payload)


if __name__ == "__main__":
    main()
