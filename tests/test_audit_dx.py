"""Cache isolation, CLI preservation and read-only command regressions."""

import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from tachyon_api.cache import (
    CacheConfig,
    InMemoryCacheBackend,
    RedisCacheBackend,
    cache,
    set_cache_config,
)
from tachyon_api.cli.main import app
from tachyon_api.cli.commands.skill import _write


def test_redis_clear_failure_never_escalates(caplog):
    client = MagicMock()
    client.flushdb.side_effect = PermissionError("denied")
    RedisCacheBackend(client).clear()
    client.flushdb.assert_called_once_with()
    client.flushall.assert_not_called()
    assert "denied" in caplog.text


def test_memory_cache_expiry_capacity_and_lru(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(
        importlib.import_module("tachyon_api.cache").time, "monotonic", lambda: now[0]
    )
    backend = InMemoryCacheBackend(max_entries=2)
    backend.set("expired", "old", ttl=1)
    now[0] += 2
    backend.set("a", "A")
    backend.set("b", "B")
    assert backend.get("expired") is None
    assert backend.get("a") == "A"
    backend.set("c", "C")
    assert backend.get("b") is None
    assert backend.get("a") == "A"
    assert backend.get("c") == "C"


def test_memory_cache_bounds_parallel_writes():
    backend = InMemoryCacheBackend(max_entries=16)

    def write(key):
        backend.set(str(key), key)
        backend.get(str(key))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(500)))
    assert len(backend._store) <= 16
    backend.clear()
    assert backend.get("499") is None


def test_explicit_cache_configs_are_isolated():
    first = CacheConfig(InMemoryCacheBackend())
    second = CacheConfig(InMemoryCacheBackend())
    calls = []

    def calculate():
        calls.append(1)
        return len(calls)

    a = cache(config=first)(calculate)
    b = cache(config=second)(calculate)
    set_cache_config(CacheConfig(InMemoryCacheBackend()))
    assert a() == a() == 1
    assert b() == b() == 2


def test_lint_no_fix_does_not_change_bytes(tmp_path, monkeypatch):
    from tachyon_api.cli.commands import lint

    source = tmp_path / "app.py"
    source.write_text("x=  1\n")
    before = source.read_bytes()
    calls = []

    def run(args):
        calls.append(args)
        return 0

    monkeypatch.setattr(lint, "_run_ruff", run)
    result = CliRunner().invoke(app, ["lint", "all", str(tmp_path), "--no-fix"])
    assert result.exit_code == 0
    assert calls == [["check", str(tmp_path)], ["format", str(tmp_path), "--check"]]
    assert source.read_bytes() == before


def test_ai_sections_preserve_user_content_and_update(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text("User instructions.\n")
    _write(path, "old", "test")
    path.write_text(path.read_text() + "\nUser footer.\n")
    _write(path, "new", "test")
    result = path.read_text()
    assert result.startswith("User instructions.\n")
    assert result.endswith("\nUser footer.\n")
    assert "old" not in result
    assert "new" in result
    _write(path, "new", "test")
    assert path.read_text() == result


@pytest.mark.parametrize(
    "value",
    [
        [],
        None,
        {"openapi": 3, "info": {}, "paths": []},
        {"openapi": "3.0.0", "info": "wrong", "paths": {}},
        {
            "openapi": "3.0.0",
            "info": {"title": "a", "version": "1"},
            "paths": {"bad": []},
        },
    ],
)
def test_openapi_basic_check_rejects_bad_types(tmp_path, value):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(value))
    result = CliRunner().invoke(app, ["openapi", "validate", str(path)])
    assert result.exit_code == 1
    assert "Invalid schema" in result.stdout


def test_ai_reference_tracks_public_exports(monkeypatch):
    import tachyon_api
    from tachyon_api.cli.templates.ai_skill import agents_md

    monkeypatch.setattr(tachyon_api, "__all__", tachyon_api.__all__ + ["audit_export"])
    monkeypatch.setattr(tachyon_api, "audit_export", lambda: None, raising=False)
    content = agents_md()
    assert "tachyon_api.audit_export" in content
    assert "tachyon openapi validate" in content
    assert "async def handler" in content
    assert "sync is correct" not in content
