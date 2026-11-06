"""Published website metrics must match their audited runtime and version."""
import json
from pathlib import Path

import pytest

from scripts.export_release_evidence import build_evidence


def test_export_is_derived_from_the_actual_versioned_audit():
    root = Path(__file__).resolve().parents[1]
    data = build_evidence(root)
    assert data == json.loads((root / "docs/release-evidence.json").read_text())
    comparison = data["comparison"]
    assert comparison["after"]["version"] == data["version"]
    assert comparison["before"]["value"] > comparison["after"]["value"] > 0


def test_a_future_release_without_an_audit_never_inherits_old_numbers(tmp_path):
    (tmp_path / "pyproject.toml").write_text('version = "9.0.0"\n')
    result = build_evidence(tmp_path)
    assert result["version"] == "9.0.0"
    assert result["comparison"] is None and result["validation"] is None


def test_mismatched_audit_version_is_rejected(tmp_path):
    (tmp_path / "pyproject.toml").write_text('version = "9.0.0"\n')
    audit = tmp_path / "docs/audits/9.0.0"
    audit.mkdir(parents=True)
    (audit / "summary.json").write_text(json.dumps({"version": "1.4.3", "all_release_gates_passed": True}))
    with pytest.raises(ValueError, match="Audit version"):
        build_evidence(tmp_path)
