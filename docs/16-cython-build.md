# 16. Cython Build

> When and how to compile Tachyon's `[fast]` extensions.

## TL;DR

```bash
pip install tachyon-api[fast]              # installs cython
python setup.py build_ext --inplace        # compile .pyx → .so
```

That's it.  Python's import system automatically prefers the compiled `.so`
modules over their `.py` siblings.  If you skip compilation (or the `.so`
files aren't present), Tachyon transparently falls back to the pure-Python
implementations.

---

## Why compile?

Tachyon's hot path is dual-implemented: every `.pyx` (Cython) module has a
matching `.py` (pure Python) version that produces identical output.  At
runtime, **whichever wins the import takes precedence** — the compiled `.so`
if compiled, otherwise the pure-Python `.py`.

| Mode | When it runs | Throughput |
|---|---|---|
| **Pure Python** *(no compilation)* | Development, CI without `[fast]`, environments without a C toolchain | Baseline (~5x FastAPI on the published benchmarks) |
| **Compiled Cython** *(`[fast]` + `build_ext --inplace`)* | Production with toolchain | +5–11% on the hot path, larger gains on parameter-heavy endpoints |

The published benchmarks in the main README are run **with** Cython compiled.
The numbers in `benchmark/profile_hotpath.py` cycle around **1.05 µs FULL
HANDLER** in compiled mode, **~1.20 µs** in pure-Python mode (~13% slower).

---

## What gets compiled

The setup builds these extensions (see `setup.py` for the canonical list):

| Source | Compiled extension | Role |
|---|---|---|
| `routing/trie.pyx` | `routing/trie.cpython-*.so` | Radix trie router (O(k) path match) |
| `processing/compiler.pyx` | `processing/compiler.cpython-*.so` | Endpoint pre-compilation (`ParamDescriptor`, `CompiledEndpoint`) |
| `processing/parameters.pyx` | `processing/parameters.cpython-*.so` | `ParameterProcessor` runtime extraction |
| `processing/response_processor.pyx` | `processing/response_processor.cpython-*.so` | Response encoding + validation |
| `processing/scope.pyx` | `processing/scope.cpython-*.so` | `TachyonScope` (lazy Starlette Request) |
| `processing/dispatch.pyx` | `processing/dispatch.cpython-*.so` | `TachyonDispatcher` (cdef class) |
| `_server_fast.pyx` | `_server_fast.cpython-*.so` | Direct `transport.write()` for HTTP/1.1 |

Everything else is pure Python (no `.pyx` counterpart).

---

## Step-by-step

### 1. Install Cython

```bash
pip install tachyon-api[fast]
```

This adds `cython>=3.0` to your environment.  The extras label is purely a
convenience for declaring the optional dependency — `pip install` does NOT
trigger compilation by itself.

### 2. Compile in place

```bash
python setup.py build_ext --inplace
```

This invokes `cythonize()` on every `.pyx` listed in `setup.py`, compiles
the generated `.c` into a platform-specific `.so`, and copies the `.so` next
to the `.py` source.

Output looks like:

```
copying build/.../tachyon_api/routing/trie.cpython-310-darwin.so       -> tachyon_api/routing
copying build/.../tachyon_api/processing/compiler.cpython-310-darwin.so -> tachyon_api/processing
copying build/.../tachyon_api/processing/parameters.cpython-310-darwin.so -> tachyon_api/processing
...
```

### 3. Verify

```python
>>> from tachyon_api.processing import parameters
>>> parameters.__file__
'.../tachyon_api/processing/parameters.cpython-310-darwin.so'
```

If you see `.py` instead of `.so`, the compiled version wasn't built or
isn't on the import path.

---

## Compiler flags

`setup.py` ships with these defaults:

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

The flags trade safety for speed — `boundscheck=False` disables bounds
checking on indexed access, `cdivision=True` uses C division semantics, etc.
These are safe in Tachyon's own hot path (verified by the test suite) but
relaxing them isn't recommended for user-written `.pyx` modules without
careful review.

---

## Falling back to pure Python

Just delete (or don't compile) the `.so` files.  Python's import system
re-resolves to the `.py` sibling:

```bash
find tachyon_api -name "*.cpython-*.so" -delete
python -c "from tachyon_api.processing import parameters; print(parameters.__file__)"
# .../tachyon_api/processing/parameters.py
```

You can run the entire test suite in both modes — it should pass identically
in both cases:

```bash
# Compiled
python setup.py build_ext --inplace
pytest tests/ -q

# Pure Python
find tachyon_api -name "*.cpython-*.so" -delete
pytest tests/ -q
```

The Tachyon CI runs both flavors to guard against drift between the `.py` and
`.pyx` implementations.

---

## Troubleshooting

### `error: command 'clang' failed with exit status 1` (macOS)

Install Xcode Command Line Tools:

```bash
xcode-select --install
```

### Compiled `.so` not picked up

- Run `python -c "import sys; print(sys.path)"` and confirm the `.so` is on
  an importable path.
- Make sure the `.so` matches your Python version: the filename includes
  `cpython-310` (or `311`, `312`, …); compiling against the wrong Python
  produces a `.so` Python silently ignores.

### Rebuilding after editing a `.pyx`

```bash
python setup.py build_ext --inplace --force
```

`--force` re-cythonizes even if the source timestamp hasn't changed.

---

## Roadmap: v1.2.9 Cython sprint

The v1.2.x SRP refactor (PRs #35 – #41) decomposed the framework into 63
single-responsibility modules with `__slots__` and full type hints — every
hot-path class is now a direct `cdef class` candidate.

The v1.2.84 audit (next sub-version) will produce a prioritized list of
modules to compile in v1.2.9, ordered by impact (µs saved per request).
Current projection: ~0.85 µs FULL HANDLER target, ~7x over FastAPI
(vs ~1.05 µs / ~5.5x today).
