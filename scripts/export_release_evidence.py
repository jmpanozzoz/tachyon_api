"""Export version-bound public website evidence from the recorded release audit."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/jmpanozzoz/tachyon_api"


def build_evidence(root: Path) -> dict:
    version = re.search(r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(), re.M)[1]
    audit = root / "docs/audits" / version
    result = {"schema_version": 1, "version": version, "comparison": None, "validation": None,
              "report_url": f"{REPO}/releases/tag/v{version}",
              "performance_note": "Operation counts are not latency or throughput measurements."}
    if not (audit / "summary.json").is_file():
        return result
    summary = json.loads((audit / "summary.json").read_text())
    if summary["version"] != version or not summary["all_release_gates_passed"]:
        raise ValueError("Audit version or completed validation differs from the release")
    digest = hashlib.sha256()
    package = root / "tachyon_api"
    for path in sorted(package.rglob("*.py")):
        digest.update(str(path.relative_to(package)).encode() + b"\0" + path.read_bytes() + b"\0")
    if digest.hexdigest() != summary["runtime_sha256_relative_paths"]:
        raise ValueError("Runtime changed since the recorded audit; do not relabel old evidence")
    result["report_url"] = f"{REPO}/tree/v{version}/docs/audits/{version}"
    rows = summary["release_matrix"]
    result["validation"] = {
        "python_versions": [row["python"] for row in rows],
        "source_tests_per_python": min(row["source_tests_passed"] for row in rows),
        "installed_wheel_contracts": min(row["installed_tests_passed"]["portable"] for row in rows),
        "http_responses": summary["endurance"]["successful"],
        "http_errors": summary["endurance"]["error_count"],
        "load_seconds": round(summary["endurance"]["seconds"], 1),
        "scope": summary["platform_limits"],
    }
    before = json.loads((audit / "di-baseline.json").read_text())
    after = json.loads((audit / "di-candidate.json").read_text())
    if after["runtime_sha256"] != digest.hexdigest():
        raise ValueError("DI measurements do not match the recorded runtime")
    comparison = json.loads(gzip.decompress((audit / "asgi-comparison.json.gz").read_bytes()))
    baseline_versions = {block["source_version"] for block in comparison["blocks"] if block["label"] == "baseline"}
    if len(baseline_versions) != 1:
        raise ValueError("Ambiguous comparison baseline")
    key = "resolve_callable_dependency"
    old, new = before["observations"][key], after["observations"][key]
    if old["nodes"] != new["nodes"] or not new["unsafe_replaced_override_rejected"]:
        raise ValueError("DI comparison does not preserve the measured contract")
    result["comparison"] = {
        "label": "Fewer repeated DI graph visits",
        "unit": "binding visits",
        "before": {"version": next(iter(baseline_versions)), "value": old["binding_visits"]},
        "after": {"version": version, "value": new["binding_visits"]},
        "context": f"Cached Depends(Class) resolution · {new['nodes']}-node singleton graph",
        "method": "Prepared binding visits counted on the same graph; lifetime and override checks retained.",
    }
    return result


if __name__ == "__main__":
    output = ROOT / "docs/release-evidence.json"
    output.write_text(json.dumps(build_evidence(ROOT), indent=2) + "\n")
    print(f"Exported {output.relative_to(ROOT)}")
