"""Check a nonempty Python package inventory and reject stale native modules."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def module_names(package_root: Path) -> list[str]:
    if not (package_root / "__init__.py").is_file():
        raise ValueError(f"Missing Python package: {package_root}")
    names = []
    for source in sorted(package_root.rglob("*.py")):
        parts = source.relative_to(package_root.parent).with_suffix("").parts
        names.append(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    if not names:
        raise ValueError("Python module inventory is empty")
    return names


def verify_python_package(package_root: Path, expected: list[str]) -> dict[str, str]:
    root = package_root.resolve()
    if not expected or set(module_names(root)) != set(expected):
        raise ValueError("Python module inventory is empty or differs from the source package")
    forbidden = {".so", ".pyd", ".dll", ".dylib", ".pyx", ".pxd"}
    stale = [str(path) for path in root.rglob("*") if path.suffix in forbidden]
    if stale:
        raise ValueError(f"Unexpected native/build sources in Python package: {stale}")
    origins = {}
    for name in expected:
        spec = importlib.util.find_spec(name)
        origin = Path(spec.origin).resolve() if spec and spec.origin else None
        if origin is None or origin.suffix != ".py" or not origin.is_relative_to(root):
            raise ValueError(f"Expected Python module inside {root}: {name} loaded {origin}")
        origins[name] = str(origin)
    return origins
