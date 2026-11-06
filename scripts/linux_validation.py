"""Inventory this host; opt in to validation on an already provisioned Linux host.

Never provisions services, connects through SSH, installs OS packages or changes
host limits. Execute only inside the agreed test environment.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def inventory():
    try:
        distribution = platform.freedesktop_os_release()
        distribution = {key: distribution[key] for key in ("ID", "VERSION_ID", "PRETTY_NAME") if key in distribution}
    except OSError:
        distribution = {}
    try:
        memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        memory = None
    disk = shutil.disk_usage(ROOT)
    return {"recorded_at": datetime.now(timezone.utc).isoformat(),
            "system": platform.system(), "architecture": platform.machine(),
            "kernel": platform.release(), "distribution": distribution,
            "cpu_count": os.cpu_count(), "physical_memory_bytes": memory,
            "disk_free_bytes": disk.free, "nofile_limits": list(resource.getrlimit(resource.RLIMIT_NOFILE)),
            "docker_available": bool(shutil.which("docker")),
            "scope": "This host only; inventory is not runtime or load validation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory outside checkout")
    parser.add_argument("--execute", action="store_true", help="Opt in to installed/source checks on Linux")
    parser.add_argument("--python", action="append", default=[], help="Supported interpreter; repeat explicitly")
    parser.add_argument("--uv", type=Path)
    parser.add_argument("--artifacts", type=Path, help="Existing wheel/sdist pair, to test the same artifact on another host")
    parser.add_argument("--duration", type=int, default=60, help="Framework smoke load duration, not multi-hour business soak")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(ROOT):
        parser.error("Use a new directory outside the checkout")
    if args.execute and (platform.system() != "Linux" or not args.python or not args.uv):
        parser.error("Execution requires Linux, explicit --python paths and --uv")
    if args.execute and (not os.getenv("TEST_DATABASE_URL") or not os.getenv("TEST_REDIS_URL")):
        parser.error("Set explicit disposable TEST_DATABASE_URL and TEST_REDIS_URL for reference integration tests")
    output.mkdir(parents=True)
    (output / "inventory.json").write_text(json.dumps(inventory(), indent=2) + "\n")
    if not args.execute:
        print("Inventory recorded. No workloads or service changes executed.")
        return 0
    command = [sys.executable, str(ROOT / "scripts/local_release.py"), "--output", str(output / "release"),
               "--uv", str(args.uv), "--duration", str(args.duration)]
    for python in args.python:
        command.extend(["--python", python])
    if args.artifacts:
        command.extend(["--artifacts", str(args.artifacts.resolve())])
    result = subprocess.run(command, cwd=ROOT, check=False)
    (output / "execution.json").write_text(json.dumps({"returncode": result.returncode,
        "scope": "See release/manifest.json for actual interpreters, artifacts and checks. Business soak is separate."}, indent=2) + "\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
