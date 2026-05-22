"""
Build Cython extensions for the tachyon_api hot path.

    pip install tachyon-api[fast]      # install with compilation
    python setup.py build_ext --inplace  # compile in-place for development

The compiled .so files are preferred over .py by Python's import system
automatically. Falls back to pure Python when .so is not present.
"""

from setuptools import setup
from setuptools.dist import Distribution

try:
    from Cython.Build import cythonize
    from setuptools import Extension
    import sys

    # Compiler flags for performance
    extra_compile_args = ["-O2"]
    if sys.platform != "win32":
        extra_compile_args += ["-ffast-math"]

    extensions = [
        Extension(
            "tachyon_api.routing.trie",
            sources=["tachyon_api/routing/trie.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.processing.compiler",
            sources=["tachyon_api/processing/compiler.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.processing.parameters",
            sources=["tachyon_api/processing/parameters.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.processing.response_processor",
            sources=["tachyon_api/processing/response_processor.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.processing.scope",
            sources=["tachyon_api/processing/scope.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.processing.dispatch",
            sources=["tachyon_api/processing/dispatch.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api._server_fast",
            sources=["tachyon_api/_server_fast.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        # v1.2.91 — Phase 1: response classes as compiled .pyx (regular class,
        # cdef class blocked by Starlette JSONResponse parent — see CHANGELOG).
        Extension(
            "tachyon_api.responses._json_response",
            sources=["tachyon_api/responses/_json_response.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.responses._bytes_response",
            sources=["tachyon_api/responses/_bytes_response.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.responses._internal_error",
            sources=["tachyon_api/responses/_internal_error.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        # v1.2.92 — Phase 2: DI resolver pipeline as cdef class (no Python
        # parent, so cdef class is viable here unlike Phase 1).
        Extension(
            "tachyon_api.processing.dependencies._override_lookup",
            sources=["tachyon_api/processing/dependencies/_override_lookup.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.processing.dependencies._scope_cache",
            sources=["tachyon_api/processing/dependencies/_scope_cache.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.processing.dependencies._circular_detector",
            sources=["tachyon_api/processing/dependencies/_circular_detector.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.processing.dependencies._class_factory",
            sources=["tachyon_api/processing/dependencies/_class_factory.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        Extension(
            "tachyon_api.processing.dependencies._resolver",
            sources=["tachyon_api/processing/dependencies/_resolver.pyx"],
            extra_compile_args=extra_compile_args,
        ),
        # v1.2.93 — Phase 3: ExceptionTable as cdef class.
        Extension(
            "tachyon_api.app._exception_table",
            sources=["tachyon_api/app/_exception_table.pyx"],
            extra_compile_args=extra_compile_args,
        ),
    ]

    setup(
        ext_modules=cythonize(
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
        ),
    )
except ImportError:
    # Cython not available — install without extensions (pure Python fallback)
    setup()
