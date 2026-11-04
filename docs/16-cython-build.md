# 16. Cython builds

Tachyon provides `.py` implementations and optional `.pyx` native extensions.
Python automatically prefers an installed native extension over its `.py`
sibling. The supported interpreter range is CPython 3.10–3.13; Python 3.14 is
excluded until the pinned msgspec release and both engines are validated.

The configured native build targets are Linux x86_64/aarch64, macOS arm64 and Windows AMD64. The 1.4.0 local publication contains macOS arm64 native wheels for all four supported CPython ABIs, a portable wheel and an sdist; the Linux/Windows native matrix was not executed for that publication. Use the portable wheel when no matching native wheel exists, or build from source. Source builds install Cython in the isolated
build environment and require a C compiler. `[fast]` also installs Cython in
the caller's environment for development. Installing it alongside a prebuilt
wheel does not rebuild that wheel.

```bash
pip install tachyon-api

# Development from a source checkout (setup.py must exist here):
cd /path/to/tachyon_api
python -m pip install -e '.[fast]' poetry-core setuptools
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
The ordinary CI workflow is configured to test the lowest/highest supported Python versions (3.10 and 3.13) in both modes. The wheel workflow is configured for all four ABIs on its target platforms, installed-wheel contracts outside the checkout, and a native rebuild from the sdist. Workflow configuration is not evidence that those hosted jobs ran.

The [dated local 1.4.0 evidence](audits/1.4.0/LOCAL_RELEASE.md) records 809 full-suite tests for each of eight interpreter/engine combinations (3.10–3.13 × Python/native), and 174 installed-wheel contracts for each portable/native installation. That run exercised macOS arm64 only; its `macosx_11_0_arm64` deployment tag does not prove testing on macOS 11. See the [local release process](quality/local-release.md) for isolated snapshots, interpreter selection, artifact hashes and publication verification. Retain such counts as dated results, not permanent suite requirements.

The experimental direct HTTP writer has been removed. The `--tachyon-server`
compatibility flag uses standard Uvicorn h11; applications should normally use
`tachyon run` or `uvicorn module:app`.

Compiler optimizations disable some Cython runtime checks. That choice is not a
general guarantee that arbitrary Cython code is safe: request semantics must be
verified by shared behavior tests in both engines.
