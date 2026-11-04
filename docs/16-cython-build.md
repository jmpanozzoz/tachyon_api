# 16. Cython builds

Tachyon provides `.py` implementations and optional `.pyx` native extensions.
Python automatically prefers an installed native extension over its `.py`
sibling. The supported interpreter range is CPython 3.10–3.13; Python 3.14 is
excluded until the pinned msgspec release and both engines are validated.

Native wheel targets: Linux x86_64/aarch64, macOS arm64, Windows AMD64.
Other platforms use source builds. Source builds install Cython in the isolated
build environment and require a C compiler. `[fast]` also installs Cython in
the caller's environment for development. Installing it alongside a prebuilt
wheel does not rebuild that wheel.

```bash
pip install tachyon-api
# Development only:
pip install 'tachyon-api[fast]'
python setup.py build_ext --inplace
```

Compilation errors fail explicitly. There is no automatic retry after a compiler
error. To build a portable `py3-none-any` wheel or install pure Python from source:

```bash
TACHYON_SKIP_CYTHON=1 python -m build --wheel
TACHYON_SKIP_CYTHON=1 pip install --no-binary=tachyon-api tachyon-api
```

Use a clean checkout/build directory for these commands. The variable controls
building, not imports: it cannot disable `.so`/`.pyd` modules already present.
Remove old native artifacts or use a clean environment before testing fallback.
The pure Python wheel still requires its normal dependencies (some include their
own native extensions).

`setup.py` discovers the checked-in `.pyx` modules and uses setuptools for wheel
tags, while reading metadata from `pyproject.toml` through poetry-core. The sdist
includes Python, Cython and declaration (`.pxd`) sources and regression tests.
CI tests the lowest/highest supported Python versions in both modes, tests
behavior outside the checkout against installed wheels, and rebuilds the sdist.

The experimental direct HTTP writer has been removed. The `--tachyon-server`
compatibility flag uses standard Uvicorn h11; applications should normally use
`tachyon run` or `uvicorn module:app`.

Compiler optimizations disable some Cython runtime checks. That choice is not a
general guarantee that arbitrary Cython code is safe: request semantics must be
verified by shared behavior tests in both engines.
