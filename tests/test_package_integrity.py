"""Release guards must reject empty inventories and leftover native modules."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.package_integrity import module_names, verify_python_package, source_hashes
from scripts.check_release_artifacts import metadata, check_wheel


def package(tmp_path):
    root = tmp_path / "tachyon_api"
    root.mkdir()
    (root / "__init__.py").touch()
    return root


def test_missing_package_or_empty_expected_inventory_fails(tmp_path):
    with pytest.raises(ValueError, match="Missing Python package"):
        module_names(tmp_path)
    with pytest.raises(ValueError, match="inventory"):
        verify_python_package(package(tmp_path), [])


@pytest.mark.parametrize("suffix", [".so", ".pyd", ".pyx", ".pxd"])
def test_stale_native_files_fail_before_import(tmp_path, monkeypatch, suffix):
    root = package(tmp_path)
    (root / f"legacy.cpython-313{suffix}").touch()
    def unexpected_import(name):
        pytest.fail("stale package attempted import")
    monkeypatch.setattr("scripts.package_integrity.importlib.util.find_spec", unexpected_import)
    with pytest.raises(ValueError, match="Unexpected native"):
        verify_python_package(root, module_names(root))


def test_installed_inventory_cannot_hide_missing_module(tmp_path):
    root = package(tmp_path)
    with pytest.raises(ValueError, match="differs"):
        verify_python_package(root, ["tachyon_api", "tachyon_api.missing"])


def test_same_module_inventory_cannot_hide_a_different_wheel(tmp_path):
    root = package(tmp_path)
    hashes = source_hashes(root)
    (root / "__init__.py").write_text("# stale or altered installed source\n")
    with pytest.raises(ValueError, match="source hashes differ"):
        verify_python_package(root, module_names(root), hashes)


def test_checkout_import_is_rejected_when_checking_installed_package(tmp_path, monkeypatch):
    root = package(tmp_path)
    monkeypatch.setattr("scripts.package_integrity.importlib.util.find_spec",
                        lambda name: SimpleNamespace(origin=str(Path('/checkout/tachyon_api/__init__.py'))))
    with pytest.raises(ValueError, match="Expected Python module inside"):
        verify_python_package(root, module_names(root))


@pytest.mark.parametrize("dependency", ["orjson>=3.11.1,<4", "orjson>=3.11.5,<4", "orjson<4"])
def test_release_metadata_rejects_vulnerable_orjson_floor(dependency):
    payload = ("Name: tachyon-api\nVersion: 1.4.1\nRequires-Python: >=3.10,<3.14\n"
               f"Requires-Dist: {dependency}\n\n").encode()
    with pytest.raises(ValueError, match="safe orjson minimum"):
        metadata(payload, "1.4.1")


def test_release_checker_rejects_native_wheel_even_with_empty_native_inventory(tmp_path):
    wheel = tmp_path / "tachyon_api-1.4.1-cp313-cp313-macosx_11_0_arm64.whl"
    with pytest.raises(ValueError, match="portable"):
        check_wheel(wheel, "1.4.1", {"tachyon_api/__init__.py"})
