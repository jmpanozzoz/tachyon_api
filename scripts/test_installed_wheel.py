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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("python", "native"), required=True)
    args = parser.parse_args()
    modules = [".".join(path.relative_to(ROOT).with_suffix("").parts)
               for path in sorted((ROOT / "tachyon_api").rglob("*.pyx"))]
    with tempfile.TemporaryDirectory(prefix="tachyon-wheel-contracts-") as folder:
        target = Path(folder)
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
            "import importlib\nfrom pathlib import Path\n"
            f"MODULES = {json.dumps(modules)}\n"
            "def test_installed_origins():\n"
            "    for name in MODULES:\n"
            "        origin = Path(importlib.import_module(name).__file__).resolve()\n"
            f"        assert not origin.is_relative_to(Path({str(ROOT)!r})), origin\n"
            f"        assert (origin.suffix in ('.so', '.pyd')) == {args.engine == 'native'!r}, origin\n"
        )
        environment = dict(os.environ, PYTHONPATH="")
        return subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=target, env=environment).returncode


if __name__ == "__main__":
    raise SystemExit(main())
