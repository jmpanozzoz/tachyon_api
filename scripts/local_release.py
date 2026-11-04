"""Prepare and test a local release in isolated snapshots; never uploads files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import re
import tarfile
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
IGNORED = shutil.ignore_patterns(".git", ".venv", ".release", ".env", ".env.*", ".pypirc", "__pycache__", "*.so", "*.pyd",
                                 "*.c", "build", "dist", "*.egg-info", ".pytest_cache", ".ruff_cache")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", action="append", required=True, help="Interpreter path; repeat for the matrix")
    parser.add_argument("--uv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New directory outside the checkout")
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--with-granian", action="store_true", help="Include optional real-server contracts")
    parser.add_argument("--artifacts", type=Path, help="Validate an existing wheel/sdist pair on another host")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(ROOT):
        parser.error("output must be a new directory outside the checkout")
    if not 1 <= args.duration < float("inf") or args.concurrency < 1:
        parser.error("duration and concurrency must be positive")
    if args.artifacts is not None and not args.artifacts.is_dir():
        parser.error("artifacts must be an existing directory containing the candidate wheel/sdist")
    output.mkdir(parents=True)
    dist = output / "dist"
    dist.mkdir()
    report = {"started": datetime.now(timezone.utc).isoformat(), "complete": False,
              "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "checks": [], "matrix": [], "artifacts": [], "with_granian": args.with_granian,
              "artifact_origin": str(args.artifacts.resolve()) if args.artifacts else "built from this source snapshot",
              "platform_limit": "Runtime tested on this host only; portable packaging is not platform execution evidence"}
    release_version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M).group(1)
    report["version"] = release_version
    environment = dict(os.environ, PYTHONPATH="")
    environment.pop("TACHYON_SKIP_CYTHON", None)

    def run(label, command, cwd, env=None):
        log = output / f"{label}.log"
        print(label, flush=True)
        with log.open("w") as stream:
            result = subprocess.run([str(x) for x in command], cwd=cwd,
                                    env=env or environment, stdout=stream, stderr=subprocess.STDOUT)
        report["checks"].append({"name": label, "exit_code": result.returncode, "log": log.name})
        if result.returncode:
            print(log.read_text()[-6000:], flush=True)
            raise RuntimeError(f"{label} failed; see {log}")

    try:
        with tempfile.TemporaryDirectory(prefix="tachyon-local-release-") as temporary:
            work = Path(temporary)
            frozen = work / "source"
            subprocess.run(["git", "clone", "--quiet", "--no-checkout", "--no-hardlinks", str(ROOT), str(frozen)], check=True)
            subprocess.run(["git", "read-tree", "HEAD"], cwd=frozen, check=True)
            shutil.copytree(ROOT, frozen, dirs_exist_ok=True, ignore=IGNORED)
            versions = set()
            for index, interpreter in enumerate(args.python):
                version = subprocess.check_output([interpreter, "-c", "import sys; print('.'.join(map(str,sys.version_info[:2])))"], text=True).strip()
                if version not in {"3.10", "3.11", "3.12", "3.13"} or version in versions:
                    raise ValueError(f"Unsupported or duplicate interpreter {version}")
                versions.add(version)
                label = "cp" + version.replace(".", "")
                source = work / label
                shutil.copytree(frozen, source)
                venv = output / f"env-{label}"
                run(f"{label}-venv", [args.uv, "venv", "--python", interpreter, venv], source)
                python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                run(f"{label}-dependencies", [args.uv, "pip", "install", "--python", python,
                    str(source) + ("[test,granian]" if args.with_granian else "[test]"),
                    *(["websockets"] if args.with_granian else []), "pytest", "pytest-asyncio", "PyJWT", "build",
                    "setuptools", "wheel", "poetry-core", "ruff==0.14.9", "twine"], source)
                run(f"{label}-ruff", [python, "-m", "ruff", "check", "tachyon_api", "tests", "benchmark", "scripts"], source)
                run(f"{label}-python", [python, "scripts/quality_cycle.py", "--engine", "python", "--output", output / f"{label}-python.json"], source)
                if index == 0:
                    if args.artifacts is None:
                        run("portable-sdist-build", [python, "-m", "build", "--no-isolation", "--outdir", dist], source)
                    else:
                        for pattern in ("*.whl", "*.tar.gz"):
                            for artifact in args.artifacts.glob(pattern):
                                shutil.copyfile(artifact, dist / artifact.name)
                        run("candidate-artifact-check", [python, "scripts/check_release_artifacts.py",
                            "--version", release_version, dist], source)
                if index == 0:
                    run("soak-python", [python, "-m", "benchmark.run_soak", "--duration", args.duration,
                        "--concurrency", args.concurrency, "--output", output / "soak-python.json"], source)
                extracted = work / f"sdist-{label}"
                extracted.mkdir()
                with tarfile.open(next(dist.glob("*.tar.gz"))) as archive:
                    # Only this run's freshly built archive is accepted.
                    for member in archive.getmembers():
                        path = Path(member.name)
                        if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                            raise ValueError(f"Unsafe sdist member {member.name}")
                    archive.extractall(extracted, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
                build_source = next(extracted.iterdir())
                run(f"{label}-sdist-wheel", [python, "-m", "build", "--wheel", "--no-isolation", "--outdir", work / f"rebuilt-{label}"], build_source)
                portable = next((work / f"rebuilt-{label}").glob("*-py3-none-any.whl"))
                run(f"{label}-install-rebuilt", [args.uv, "pip", "install", "--python", python, "--no-deps", "--reinstall", portable], source)
                run(f"{label}-installed-rebuilt", [python, "scripts/test_installed_wheel.py"], source)
                candidate = next(dist.glob("*-py3-none-any.whl"))
                run(f"{label}-install-portable", [args.uv, "pip", "install", "--python", python, "--no-deps", "--reinstall", candidate], source)
                run(f"{label}-installed-portable", [python, "scripts/test_installed_wheel.py"], source)
                report["matrix"].append({"python": version, "engines": ["python"], "wheel": candidate.name})
            run("artifact-check", [python, "scripts/check_release_artifacts.py", "--version", release_version, dist], frozen)
            run("metadata-check", [python, "-m", "twine", "check", "--strict", *sorted(dist.iterdir())], frozen)
            for artifact in sorted(dist.iterdir()):
                report["artifacts"].append({"file": "dist/" + artifact.name,
                    "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(), "bytes": artifact.stat().st_size})
            report["complete"] = True
    finally:
        report["finished"] = datetime.now(timezone.utc).isoformat()
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
