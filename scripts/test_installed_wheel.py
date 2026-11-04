"""Exercise an installed wheel outside the source tree and its pytest config."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.package_integrity import module_names  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("python",), default="python")
    parser.parse_args()
    modules = module_names(ROOT / "tachyon_api")
    with tempfile.TemporaryDirectory(prefix="tachyon-wheel-contracts-") as folder:
        target = Path(folder)
        shutil.copyfile(ROOT / "scripts/package_integrity.py", target / "package_integrity.py")
        tests = target / "tests"
        tests.mkdir()
        (tests / "__init__.py").touch()
        names = ["helpers.py", "test_audit_wheel.py", "test_audit_routing_contract.py", "test_local_release_runtime.py"]
        names += [path.name for path in sorted((ROOT / "tests").glob("test_continuous_*.py"))]
        for name in names:
            shutil.copyfile(ROOT / "tests" / name, tests / name)
        (target / "pytest.ini").write_text("[pytest]\nasyncio_mode = strict\nasyncio_default_fixture_loop_scope = function\n")
        # A config inherited from the checkout can silently put source ahead of
        # the installed package. Assert every extension origin in this process.
        (tests / "test_install_origin.py").write_text(
            "import importlib.util\nfrom pathlib import Path\n"
            "from package_integrity import verify_python_package\n"
            f"MODULES = {json.dumps(modules)}\n"
            "def test_installed_origins():\n"
            "    root = Path(importlib.util.find_spec('tachyon_api').origin).resolve().parent\n"
            f"    assert not root.is_relative_to(Path({str(ROOT)!r})), root\n"
            "    assert verify_python_package(root, MODULES)\n"
        )
        environment = dict(os.environ, PYTHONPATH="")
        return subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=target, env=environment).returncode


if __name__ == "__main__":
    raise SystemExit(main())
