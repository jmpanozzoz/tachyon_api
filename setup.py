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
