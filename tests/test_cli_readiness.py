"""CLI diagnostics must be read-only and generated applications executable."""
import json
import os
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from tachyon_api.cli.main import app

runner = CliRunner()


def test_doctor_does_not_import_app_connect_or_write_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:DO-NOT-EXPOSE@unreachable/db")
    monkeypatch.setenv("REDIS_URL", "redis://:DO-NOT-EXPOSE@unreachable/0")
    (tmp_path / "app.py").write_text('raise RuntimeError("must not import")')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["ok"] is True
    assert "DO-NOT-EXPOSE" not in result.output
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_doctor_import_failure_redacts_application_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "readiness_bad_app.py").write_text('print("DO-NOT-EXPOSE")\nraise ValueError("DO-NOT-EXPOSE")')
    result = runner.invoke(app, ["doctor", "--app", "readiness_bad_app:app", "--json"])
    assert result.exit_code == 1
    assert "DO-NOT-EXPOSE" not in result.output
    assert json.loads(result.output)["checks"][-1]["ok"] is False


def test_routes_json_includes_websocket_when_requested(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "readiness_routes_app.py").write_text('''from tachyon_api import Tachyon
app = Tachyon()
@app.get("/health")
async def health(): return {}
@app.websocket("/ws")
async def socket(websocket): pass
''')
    result = runner.invoke(app, ["routes", "readiness_routes_app:app", "--json", "--include-websockets"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["routes"]
    assert {r["protocol"] for r in rows} == {"http", "websocket"}



@pytest.mark.parametrize("profile", ["minimal", "postgres"])
def test_generated_project_runs_tests_and_exports_openapi_outside_checkout(tmp_path, profile):
    result = runner.invoke(app, ["new", "sample", "--path", str(tmp_path), "--profile", profile])
    assert result.exit_code == 0, result.output
    project = tmp_path / "sample"
    env = {**os.environ, "PYTHONPATH": "", "PYTEST_ADDOPTS": ""}
    env.pop("DATABASE_URL", None)
    # The interpreter is installed/editable; cwd is not this repository.
    command = [sys.executable, "-m", "pytest", "tests/", "-q", "-o", "asyncio_mode=strict"]
    run = subprocess.run(command, cwd=project, env=env, text=True, capture_output=True)
    assert run.returncode == 0, run.stdout + run.stderr
    if profile == "minimal":
        assert "1 passed" in run.stdout
    else:
        assert "1 skipped" in run.stdout  # DB integration has a separate explicit gate.
    schema = subprocess.run([sys.executable, "-m", "tachyon_api.cli", "openapi", "export", "app:app"],
                            cwd=project, env=env, text=True, capture_output=True)
    assert schema.returncode == 0, schema.stderr
    assert json.loads(schema.stdout)["paths"]


def test_unknown_profile_and_component_collisions_do_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["new", "sample", "--profile", "missing"])
    assert result.exit_code == 1 and not (tmp_path / "sample").exists()
    destination = tmp_path / "modules" / "note" / "note_controller.py"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"owned by user")
    result = runner.invoke(app, ["g", "controller", "note"])
    assert result.exit_code == 1
    assert destination.read_bytes() == b"owned by user"


def test_strict_openapi_rejects_invalid_operation(tmp_path):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps({"openapi": "3.0.0", "info": {"title": "test", "version": "1"},
                                "paths": {"/": {"get": {"responses": "invalid"}}}}))
    assert runner.invoke(app, ["openapi", "validate", str(path)]).exit_code == 0
    assert runner.invoke(app, ["openapi", "validate", str(path), "--strict"]).exit_code == 1
