"""A failed local release gate must stop before the publication command."""
import hashlib
import json
import sys

import pytest

from scripts import publish_local


@pytest.mark.parametrize("version", [(3, 9), (3, 14), (4, 0)])
def test_quality_cycle_rejects_unsupported_python_before_importing_runtime(tmp_path, monkeypatch, version):
    from scripts import quality_cycle
    monkeypatch.setattr(sys, "version_info", version)
    monkeypatch.setattr(sys, "argv", ["quality_cycle", "--output", str(tmp_path / "quality.json")])

    def unexpected_runtime(*args, **kwargs):
        pytest.fail("unsupported interpreter imported the runtime")

    monkeypatch.setattr(quality_cycle, "verify_python_package", unexpected_runtime)
    with pytest.raises(SystemExit, match="2"):
        quality_cycle.main()
    assert not (tmp_path / "quality.json").exists()


@pytest.mark.parametrize("failure", ["incomplete", "failed-check", "changed-artifact", "outside-dist", "empty-artifacts"])
def test_publication_rejects_incomplete_or_changed_release(tmp_path, monkeypatch, failure):
    dist = tmp_path / "dist"
    dist.mkdir()
    artifact = dist / "example.whl"
    artifact.write_bytes(b"validated artifact")
    report = {"complete": True, "checks": [{"exit_code": 0}],
              "artifacts": [{"file": "dist/example.whl", "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}]}
    if failure == "incomplete":
        report["complete"] = False
    elif failure == "failed-check":
        report["checks"][0]["exit_code"] = 1
    elif failure == "changed-artifact":
        artifact.write_bytes(b"unverified replacement")
    elif failure == "outside-dist":
        report["artifacts"][0]["file"] = "../outside.whl"
    else:
        report["artifacts"] = []
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(report))
    monkeypatch.setattr(sys, "argv", ["publish_local", "--manifest", str(manifest), "--uv", "uv"])
    def unexpected_upload(*args, **kwargs):
        pytest.fail("failed gate attempted publication")
    monkeypatch.setattr(publish_local.subprocess, "run", unexpected_upload)
    with pytest.raises(SystemExit, match="2"):
        publish_local.main()
