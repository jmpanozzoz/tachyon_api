"""Run the local release quality gates and retain machine-readable evidence.

Run with each supported interpreter, before and after building extensions.
This command verifies the current working tree; it never edits or commits it.
"""
from __future__ import annotations

import argparse
import importlib.util
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", choices=("python", "native"), required=True)
    args = parser.parse_args()
    modules = {}
    for source in sorted((ROOT / "tachyon_api").rglob("*.pyx")):
        name = ".".join(source.relative_to(ROOT).with_suffix("").parts)
        spec = importlib.util.find_spec(name)
        origin = spec.origin if spec is not None else None
        if origin is None or origin.endswith((".so", ".pyd")) != (args.engine == "native"):
            parser.error(f"Expected {args.engine} engine for {name}; loaded {origin}")
        modules[name] = origin
    commands = [
        [sys.executable, "scripts/check_py_pyx_parity.py"],
        [sys.executable, "-m", "pytest", "tests", "example/tests", "-q"],
    ]
    digest = hashlib.sha256()
    inputs = [ROOT / "pyproject.toml", ROOT / "poetry.lock", ROOT / "setup.py", ROOT / "MANIFEST.in", ROOT / "pytest.ini", ROOT / "README.md"]
    for directory in ("tachyon_api", "tests", "example", "scripts", "benchmark", "docs", ".github/workflows"):
        inputs.extend(path for path in (ROOT / directory).rglob("*")
                      if path.suffix in (".py", ".pyx", ".pxd", ".yml", ".md"))
    for path in sorted(inputs):
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0")
    report = {"inputs_sha256": digest.hexdigest(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "engine": args.engine,
        "modules": modules,
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True),
        "checks": [],
    }
    for command in commands:
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(result.stdout, end="", flush=True)
        report["checks"].append({"command": command, "exit_code": result.returncode,
                                 "seconds": time.monotonic() - started, "output": result.stdout})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    return int(any(check["exit_code"] for check in report["checks"]))


if __name__ == "__main__":
    raise SystemExit(main())
