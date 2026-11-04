"""Publish only the artifacts in a completed local release manifest to PyPI."""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--uv", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    report = json.loads(manifest.read_text())
    if not report.get("complete") or not report.get("checks") or any(check["exit_code"] for check in report["checks"]):
        parser.error("Local release gates are incomplete or failed")
    root = manifest.parent
    artifacts = []
    for artifact in report["artifacts"]:
        path = (root / artifact["file"]).resolve()
        if not path.is_relative_to(root) or path.parent != root / "dist":
            parser.error("Artifact must be inside this release's dist directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            parser.error(f"Artifact changed after validation: {path.name}")
        artifacts.append(path)
    if not artifacts:
        parser.error("Manifest contains no artifacts")
    environment = dict(os.environ)
    token = next((environment.get(name) for name in ("UV_PUBLISH_TOKEN", "TWINE_PASSWORD", "PYPI_TOKEN", "PYPI_API_TOKEN")
                  if environment.get(name)), None)
    if token is None:
        config = configparser.ConfigParser(interpolation=None)
        config.read(Path.home() / ".pypirc")
        if config.get("pypi", "username", fallback="__token__") == "__token__":
            token = config.get("pypi", "password", fallback=None)
    if token:
        environment["UV_PUBLISH_TOKEN"] = token
    elif not args.dry_run:
        parser.error("No PyPI token configured in environment or ~/.pypirc [pypi]")
    command = [str(args.uv), "publish", "--no-config", "--trusted-publishing", "never",
               "--publish-url", "https://upload.pypi.org/legacy/", *map(str, artifacts)]
    if args.dry_run:
        command.append("--dry-run")
    subprocess.run(command, env=environment, check=True)
    if not args.dry_run:
        version = report["version"]
        with urllib.request.urlopen(f"https://pypi.org/pypi/tachyon-api/{version}/json", timeout=30) as response:
            published = json.load(response)
        remote = {item["filename"]: item["digests"]["sha256"] for item in published["urls"]}
        for artifact in report["artifacts"]:
            if remote.get(Path(artifact["file"]).name) != artifact["sha256"]:
                raise RuntimeError("Publication completed but remote artifact verification failed; do not rebuild or overwrite the release")
        print(f"Verified tachyon-api {version} on PyPI: {len(artifacts)} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
