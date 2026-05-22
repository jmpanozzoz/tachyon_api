#!/usr/bin/env python3
"""
.py ↔ .pyx parity check.

For every `.pyx` module that has a sibling `.py` (the pure-Python fallback),
verify that they expose the same public API:
  - Same set of public top-level functions
  - Same set of public top-level classes
  - For each shared class: same set of public method names

Catches the kind of silent divergence introduced in v1.2.85, where the
pure-Python parameter pipeline got a security fix (null-byte rejection,
2 MB body limit) that the Cython version missed because nobody re-read
the .pyx file.

This script is a STRUCTURAL check.  It cannot detect logic divergence —
that's the job of the test suite (which runs in both modes via CI).

Exit codes:
  0 — all pairs aligned
  1 — at least one pair has mismatched public surface
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tachyon_api"

# `.pyx` files that intentionally have no `.py` sibling.
PYX_ONLY_WHITELIST = {
    "tachyon_api/_server_fast.pyx",  # low-level perf module, Cython-only by design
}


def public(name: str) -> bool:
    """Top-level public name — single-leading-underscore symbols are private."""
    return not name.startswith("_")


def extract_py_surface(path: Path) -> tuple[set[str], set[str], dict[str, set[str]]]:
    """Return (functions, classes, methods-by-class) for a .py file."""
    tree = ast.parse(path.read_text())
    funcs: set[str] = set()
    classes: set[str] = set()
    methods: dict[str, set[str]] = {}

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if public(node.name):
                funcs.add(node.name)
        elif isinstance(node, ast.ClassDef):
            if public(node.name):
                classes.add(node.name)
                ms: set[str] = set()
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if public(sub.name) or sub.name == "__init__":
                            ms.add(sub.name)
                methods[node.name] = ms
    return funcs, classes, methods


# Regex-based scan for .pyx files (no Python ast for Cython grammar).
_DEF_RX = re.compile(
    r"^\s*(?:async\s+)?(?:cpdef|cdef|def)\s+(?:[a-zA-Z_][\w\[\]\.,\s*]*\s+)?([a-zA-Z_]\w*)\s*\(",
    re.MULTILINE,
)
_CLASS_RX = re.compile(r"^\s*(?:cdef\s+)?class\s+([a-zA-Z_]\w*)\s*[:\(]", re.MULTILINE)


def extract_pyx_surface(path: Path) -> tuple[set[str], set[str], dict[str, set[str]]]:
    """Return (functions, classes, methods-by-class) for a .pyx file.

    Uses regex — Cython's grammar isn't covered by `ast`.  Good enough for
    the structural surface check because we only care about top-level names
    and method names, not body content.
    """
    text = path.read_text()
    # Strip comments and docstrings (rough but good enough — we don't want
    # to match `class` or `def` mentioned inside strings).
    text = re.sub(r'""".*?"""', "", text, flags=re.DOTALL)
    text = re.sub(r"'''.*?'''", "", text, flags=re.DOTALL)
    text = re.sub(r"#[^\n]*", "", text)

    classes: set[str] = set()
    methods: dict[str, set[str]] = {}
    funcs: set[str] = set()

    # Walk line by line tracking class indent
    current_class: str | None = None
    class_indent: int = -1
    for raw_line in text.splitlines():
        # Skip blank lines but don't change class state on them
        if not raw_line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip())

        # Leaving the class block
        if current_class is not None and indent <= class_indent:
            current_class = None
            class_indent = -1

        # Class definition
        m_cls = _CLASS_RX.match(raw_line)
        if m_cls:
            cname = m_cls.group(1)
            if public(cname):
                classes.add(cname)
                methods.setdefault(cname, set())
                current_class = cname
                class_indent = indent
            else:
                current_class = None
            continue

        # Def / cpdef / cdef function
        m_def = _DEF_RX.match(raw_line)
        if m_def:
            fname = m_def.group(1)
            if current_class is not None:
                if public(fname) or fname == "__init__":
                    methods[current_class].add(fname)
            elif indent == 0:
                if public(fname):
                    funcs.add(fname)

    return funcs, classes, methods


def relpath(p: Path) -> str:
    return str(p.relative_to(ROOT))


def check_pair(pyx_path: Path) -> list[str]:
    """Compare the public surface of `pyx_path` with its `.py` sibling.

    Returns a list of human-readable mismatch messages.  Empty list = OK.
    """
    py_path = pyx_path.with_suffix(".py")
    msgs: list[str] = []
    if not py_path.exists():
        if relpath(pyx_path) not in PYX_ONLY_WHITELIST:
            msgs.append(
                f"{relpath(pyx_path)}: no .py sibling "
                f"(add to PYX_ONLY_WHITELIST if intentional)"
            )
        return msgs

    py_funcs, py_classes, py_methods = extract_py_surface(py_path)
    pyx_funcs, pyx_classes, pyx_methods = extract_pyx_surface(pyx_path)

    only_in_py_funcs = py_funcs - pyx_funcs
    only_in_pyx_funcs = pyx_funcs - py_funcs
    if only_in_py_funcs:
        msgs.append(
            f"{relpath(pyx_path)}: functions in .py but not .pyx: "
            f"{sorted(only_in_py_funcs)}"
        )
    if only_in_pyx_funcs:
        msgs.append(
            f"{relpath(pyx_path)}: functions in .pyx but not .py: "
            f"{sorted(only_in_pyx_funcs)}"
        )

    only_in_py_classes = py_classes - pyx_classes
    only_in_pyx_classes = pyx_classes - py_classes
    if only_in_py_classes:
        msgs.append(
            f"{relpath(pyx_path)}: classes in .py but not .pyx: "
            f"{sorted(only_in_py_classes)}"
        )
    if only_in_pyx_classes:
        msgs.append(
            f"{relpath(pyx_path)}: classes in .pyx but not .py: "
            f"{sorted(only_in_pyx_classes)}"
        )

    for cls in py_classes & pyx_classes:
        only_py = py_methods.get(cls, set()) - pyx_methods.get(cls, set())
        only_pyx = pyx_methods.get(cls, set()) - py_methods.get(cls, set())
        if only_py:
            msgs.append(
                f"{relpath(pyx_path)}: class {cls} methods in .py but not .pyx: "
                f"{sorted(only_py)}"
            )
        if only_pyx:
            msgs.append(
                f"{relpath(pyx_path)}: class {cls} methods in .pyx but not .py: "
                f"{sorted(only_pyx)}"
            )

    return msgs


def main(argv: Iterable[str]) -> int:
    pyx_files = sorted(PKG.rglob("*.pyx"))
    if not pyx_files:
        print("ERROR: no .pyx files found under tachyon_api/", file=sys.stderr)
        return 1

    all_msgs: list[str] = []
    pairs_checked = 0
    for pyx in pyx_files:
        if pyx.with_suffix(".py").exists():
            pairs_checked += 1
        all_msgs.extend(check_pair(pyx))

    if all_msgs:
        print("✗ .py ↔ .pyx parity check FAILED\n")
        for m in all_msgs:
            print(f"  • {m}")
        print(
            f"\nChecked {pairs_checked} .py/.pyx pair(s); "
            f"{len(all_msgs)} mismatch(es) found."
        )
        return 1

    print(
        f"✓ .py ↔ .pyx parity check passed "
        f"({pairs_checked} pair(s), {len(pyx_files)} .pyx total)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
