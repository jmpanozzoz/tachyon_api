"""Run the local release quality gates and retain machine-readable evidence.

Run with each supported interpreter against the Python implementation.
This command verifies the current working tree; it never edits or commits it.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.package_integrity import module_names, verify_python_package  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", choices=("python",), default="python")
    args = parser.parse_args()
    if not (3, 10) <= sys.version_info[:2] < (3, 14):
        parser.error("Unsupported Python: use Python 3.10 through 3.13")
    try:
        package = ROOT / "tachyon_api"
        modules = verify_python_package(package, module_names(package))
    except ValueError as exc:
        parser.error(str(exc))
    commands = [
        [sys.executable, "-m", "pytest", "tests", "example/tests", "-q"],
    ]
    digest = hashlib.sha256()
    inputs = [ROOT / "pyproject.toml", ROOT / "poetry.lock", ROOT / "setup.py", ROOT / "MANIFEST.in", ROOT / "pytest.ini", ROOT / "README.md", ROOT / ".gitattributes", ROOT / "scripts/test-requirements.txt", ROOT / "docs/release-evidence.json"]
    for directory in ("tachyon_api", "tests", "example", "scripts", "benchmark", "docs", ".github/workflows"):
        inputs.extend(path for path in (ROOT / directory).rglob("*")
                      if path.suffix in (".py", ".pyx", ".pxd", ".yml", ".yaml", ".md", ".txt", ".ini", ".mako", ".toml")
                      or path.name in ("Dockerfile", ".coveragerc", ".env.example"))
    for path in sorted(inputs):
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0")
    report = {"inputs_sha256": digest.hexdigest(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "python_executable": sys.executable,
        "dependency_resolution": "installed versions; poetry.lock is fingerprinted, not enforced by this runner",
        "platform": platform.platform(),
        "engine": args.engine,
        "modules": modules,
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True),
        "checks": [],
    }
    report["dependency_versions"] = {}
    for package in ("tachyon-api", "starlette", "uvicorn", "httptools", "msgspec", "orjson", "typer", "python-multipart", "granian", "pytest", "pytest-asyncio", "httpx", "PyJWT", "websockets", "ruff", "SQLAlchemy", "asyncpg", "alembic", "redis", "argon2-cffi", "asgi-lifespan", "openapi-spec-validator"):
        try:
            report["dependency_versions"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report["dependency_versions"][package] = None
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
