# 16. Cython Build

> How Tachyon ships compiled extensions, and what to do when no prebuilt wheel is available for your platform.

## TL;DR

```bash
pip install tachyon-api   # precompiled .so on supported platforms — nothing else needed
```

Tachyon's hot path is implemented in both pure Python (`.py`) and Cython (`.pyx`). Published wheels include the compiled `.so` binaries. Python's import system automatically prefers `.so` over `.py`, so the compiled path is active by default with no configuration required.

---

## Supported wheel platforms

| Platform | Architectures | CPython |
|---|---|---|
| Linux | x86_64, aarch64 | 3.10 · 3.11 · 3.12 · 3.13 |
| macOS | arm64 (Apple Silicon) | 3.10 · 3.11 · 3.12 · 3.13 |
| Windows | x86_64 | 3.10 · 3.11 · 3.12 · 3.13 |

20 wheels are published per release (4 Python versions × 5 platform legs).

---

## Why are extensions compiled?

Tachyon's hot path is dual-implemented: every `.pyx` (Cython) module has a
matching `.py` (pure Python) sibling that produces identical output. At
runtime, whichever wins the import takes precedence — the compiled `.so`
if present, otherwise the `.py` fallback.

| Mode | Throughput delta |
|---|---|
| **Pure Python** | Baseline — still ~5x faster than FastAPI |
| **Compiled Cython** | +14% total; up to +18% on DI-heavy endpoints |

The benchmark numbers in the README are measured with the compiled path, which is what `pip install tachyon-api` gives you on supported platforms.

---

## What gets compiled (27 modules)

| Module | Role |
|---|---|
| `routing/trie` | Radix trie router — O(k) path match |
| `processing/compiler` | Endpoint pre-compilation (`CompiledEndpoint`, `ParamDescriptor`) |
| `processing/parameters` | `ParameterPipeline` orchestrator |
| `processing/response_processor` | Response encoding + validation |
| `processing/scope` | `TachyonScope` (lazy Starlette Request) |
| `processing/dispatch` | `TachyonDispatcher` (`cdef class`) |
| `processing/dependencies/_override_lookup` | DI override resolution |
| `processing/dependencies/_scope_cache` | Per-scope instance cache |
| `processing/dependencies/_circular_detector` | Circular dependency guard |
| `processing/dependencies/_class_factory` | `@injectable` class instantiation |
| `processing/dependencies/_resolver` | Full DI resolver pipeline |
| `processing/_extractors/_missing` | Missing-param sentinel |
| `processing/_extractors/header` | Header extraction |
| `processing/_extractors/cookie` | Cookie extraction |
| `processing/_extractors/query` | Single query param extraction |
| `processing/_extractors/query_list` | List query param extraction |
| `processing/_extractors/path` | Path param extraction + type conversion |
| `processing/_extractors/body` | Body extraction + msgspec decode |
| `processing/_extractors/body_limit` | Body size limiter |
| `processing/_extractors/form` | Form data extraction |
| `processing/_extractors/file` | File upload extraction |
| `responses/_json_response` | `TachyonJSONResponse` |
| `responses/_bytes_response` | `TachyonBytesResponse` |
| `responses/_internal_error` | `_InternalErrorResponse` |
| `app/_exception_table` | Exception handler table |
| `security/_bearer_parser` | Bearer token header parser |
| `_server_fast` | Direct `transport.write()` for HTTP/1.1 |

---

## Source builds (no wheel for your platform)

If `pip install tachyon-api` falls back to the sdist (no matching wheel), it
will attempt to compile the extensions from the `.pyx` sources. This requires:

1. A C compiler (`gcc` on Linux, `clang` via Xcode Command Line Tools on macOS)
2. Cython — install via the `[fast]` extra:

```bash
pip install tachyon-api[fast]   # pulls in cython>=3.0
```

If Cython is present in the build environment when installing from sdist, the
extensions are compiled automatically. If it's absent or compilation fails,
`pip` installs a pure-Python wheel and logs a warning — the framework still
works, just without the +14% Cython boost.

---

## Verifying which path is active

```python
import tachyon_api.routing.trie as trie
print(trie.__file__)
# compiled:    .../tachyon_api/routing/trie.cpython-312-darwin.so
# pure Python: .../tachyon_api/routing/trie.py
```

---

## Development: compiling in-place

For contributors working on the `.pyx` sources:

```bash
pip install cython>=3.0
python setup.py build_ext --inplace
```

After editing a `.pyx` file:

```bash
python setup.py build_ext --inplace --force   # force re-cythonize
```

To test the pure-Python fallback path:

```bash
find tachyon_api -name "*.cpython-*.so" -delete
pytest tests/ -q   # should pass identically
```

Tachyon CI runs both modes (compiled + pure-Python) on every PR to guard against drift between the `.py` and `.pyx` implementations.

---

## Compiler flags

`setup.py` applies these defaults to all extensions:

```python
extra_compile_args = ["-O2"]
if sys.platform != "win32":
    extra_compile_args += ["-ffast-math"]

cythonize(
    extensions,
    compiler_directives={
        "language_level": "3",
        "boundscheck": False,
        "wraparound": False,
        "nonecheck": False,
        "cdivision": True,
        "embedsignature": False,
    },
)
```

These trade safety checks for speed. They are safe in Tachyon's own hot path (verified by the 370-test suite in both compiled and pure-Python mode), but are not recommended for user-written `.pyx` modules without review.

---

## Troubleshooting

### `error: command 'clang' failed` (macOS)

```bash
xcode-select --install
```

### Compiled `.so` not picked up after in-place build

Confirm the `.so` matches your Python version — the filename includes
`cpython-310` (or `311`, `312`, …). A `.so` compiled against the wrong
Python is silently ignored:

```bash
python -c "import sys; print(sys.version_info)"
ls tachyon_api/routing/trie*.so
```

### `TACHYON_SKIP_CYTHON=1`

Set this environment variable to force a pure-Python install even when Cython
is available in the build environment. Used internally by CI to verify the
pure-Python fallback path:

```bash
TACHYON_SKIP_CYTHON=1 pip install -e .
```
