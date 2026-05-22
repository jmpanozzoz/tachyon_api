"""Build script invoked by poetry-core to add Cython extensions.

Configured via `[tool.poetry.build] script = "_build.py"` with
`generate-setup-file = true` so poetry-core generates a setup.py that calls
`build(setup_kwargs)` here. The file is named `_build.py` (not `build.py`)
to avoid shadowing the PEP 517 frontend package `build` when running
`python -m build` from the project root.

If Cython is unavailable the wheel is built as pure-Python; runtime imports
fall back to the `.py` modules transparently.

Keep PYX_MODULES in sync with setup.py. `scripts/check_py_pyx_parity.py`
guards against `.py` / `.pyx` sibling drift.
"""

from __future__ import annotations

import sys
from typing import Any

PYX_MODULES: list[str] = [
    "tachyon_api.routing.trie",
    "tachyon_api.processing.compiler",
    "tachyon_api.processing.parameters",
    "tachyon_api.processing.response_processor",
    "tachyon_api.processing.scope",
    "tachyon_api.processing.dispatch",
    "tachyon_api._server_fast",
    "tachyon_api.responses._json_response",
    "tachyon_api.responses._bytes_response",
    "tachyon_api.responses._internal_error",
    "tachyon_api.processing.dependencies._override_lookup",
    "tachyon_api.processing.dependencies._scope_cache",
    "tachyon_api.processing.dependencies._circular_detector",
    "tachyon_api.processing.dependencies._class_factory",
    "tachyon_api.processing.dependencies._resolver",
    "tachyon_api.app._exception_table",
    "tachyon_api.processing._extractors._missing",
    "tachyon_api.processing._extractors.header",
    "tachyon_api.processing._extractors.cookie",
    "tachyon_api.processing._extractors.query",
    "tachyon_api.processing._extractors.path",
    "tachyon_api.processing._extractors.body_limit",
    "tachyon_api.processing._extractors.body",
    "tachyon_api.processing._extractors.form",
    "tachyon_api.processing._extractors.file",
    "tachyon_api.processing._extractors.query_list",
    "tachyon_api.security._bearer_parser",
]


def build(setup_kwargs: dict[str, Any]) -> None:
    try:
        from Cython.Build import cythonize
        from setuptools import Extension
    except ImportError:
        return

    extra_compile_args = ["-O2"]
    if sys.platform != "win32":
        extra_compile_args.append("-ffast-math")

    extensions = [
        Extension(
            name=mod,
            sources=[mod.replace(".", "/") + ".pyx"],
            extra_compile_args=extra_compile_args,
        )
        for mod in PYX_MODULES
    ]

    setup_kwargs["ext_modules"] = cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "nonecheck": False,
            "cdivision": True,
            "embedsignature": False,
        },
        annotate=False,
    )
