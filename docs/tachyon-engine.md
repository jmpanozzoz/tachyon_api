# Tachyon Engine - Rust-Powered Performance

## Overview

Tachyon API v1.0.0+ includes infrastructure for **tachyon-engine**, a Rust-powered ASGI implementation that aims to provide significant performance improvements over Starlette.

## Current Status (v1.0.0)

🚧 **Experimental**: tachyon-engine v0.1.0 has an incomplete ASGI protocol implementation and is not production-ready.

✅ **Stable Default**: Tachyon API v1.0.0 uses Starlette by default, ensuring 100% production stability.

🎯 **Future Ready**: Complete adapter infrastructure is in place. When tachyon-engine v0.2.0+ is released with full ASGI support, switching will be seamless.

---

## Performance Goals

When tachyon-engine is production-ready, expected improvements:

| Metric | Improvement |
|--------|-------------|
| **Request Creation** | 2-3x faster |
| **Path Matching** | 10x faster |
| **JSON Serialization** | 1.7x faster |
| **Overall Throughput** | 2-4x faster |
| **Memory Usage** | 30-50% reduction |

---

## Installation

```bash
# Standard installation (uses Starlette)
pip install tachyon-api

# With experimental tachyon-engine support
pip install tachyon-api[engine]
```

---

## Configuration

### Default (Stable - Starlette)

```python
from tachyon_api import Tachyon

# Uses Starlette (stable, production-ready)
app = Tachyon()
```

### Explicit Engine Selection

```python
from tachyon_api import Tachyon, AsgiEngine

# Explicitly use Starlette
app = Tachyon(engine=AsgiEngine.STARLETTE)

# Experimental: Use tachyon-engine (requires v0.2.0+ for production)
app = Tachyon(engine=AsgiEngine.TACHYON)

# Auto-detect (currently defaults to Starlette)
app = Tachyon(engine=AsgiEngine.AUTO)
```

### Environment Variable

```bash
# Force Starlette
export TACHYON_ENGINE=starlette

# Experimental: Force tachyon-engine
export TACHYON_ENGINE=tachyon

# Auto-detect (default)
export TACHYON_ENGINE=auto
```

---

## Architecture

### Adapter Pattern

Tachyon v1.0.0 uses an **adapter pattern** for engine abstraction:

```
┌─────────────────────┐
│   Tachyon API       │
│  (Your Code)        │
└──────────┬──────────┘
           │
    ┌──────▼──────────────┐
    │  AsgiEngine Config  │
    │   (AUTO/STARLETTE/  │
    │     TACHYON)        │
    └──────┬──────────────┘
           │
    ┌──────▼──────────┬─────────────┐
    │                 │             │
┌───▼────────┐  ┌────▼─────────┐   │
│ Starlette  │  │  tachyon-    │   │
│  Adapter   │  │   engine     │   │
│  (Stable)  │  │  Adapter     │   │
│            │  │ (Experimental)│   │
└────────────┘  └──────────────┘   │
    ✅ v1.0.0      🚧 Waiting for   │
                   engine v0.2.0+   │
```

### Adapter Interfaces

All implemented adapters support:
- ✅ HTTP routing with path parameters
- ✅ Request/Response objects
- ✅ WebSocket support
- ✅ Middleware stacking
- ✅ File uploads
- ✅ Cookie/Header handling
- ✅ Dependency injection

---

## tachyon-engine Status

### v0.1.0 (Current - Experimental)

**What Works**:
- ✅ Basic ASGI structure
- ✅ Request/Response objects
- ✅ Path matching
- ✅ WebSocket objects (structure)

**What Needs Work**:
- 🚧 Complete ASGI protocol implementation
- 🚧 Response completion signaling
- 🚧 Middleware execution
- 🚧 Form data parsing
- 🚧 File upload handling

### v0.2.0+ (Planned)

When these are complete:
1. Full ASGI 3.0 protocol support
2. All 223 tachyon-api tests passing
3. Performance benchmarks validated
4. Production-ready status

**Then**: Simply change one line in `engine_config.py` to make tachyon-engine the default.

---

## Migration Path

### For Tachyon API Users (v1.0.0)

**No changes needed!** Everything works with Starlette by default.

```python
# Your existing code works exactly the same
from tachyon_api import Tachyon, Struct, Body, Query

app = Tachyon()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"user_id": user_id}

# Uses Starlette adapter - 100% stable ✅
```

### When tachyon-engine v0.2.0+ Is Ready

**Option 1**: Explicit (Recommended for testing)
```python
from tachyon_api import Tachyon, AsgiEngine

app = Tachyon(engine=AsgiEngine.TACHYON)
```

**Option 2**: Environment variable
```bash
export TACHYON_ENGINE=tachyon
python app.py
```

**Option 3**: Wait for auto-detection
- When tachyon-engine is stable, AUTO mode will prefer it
- No code changes needed

---

## Development of tachyon-engine

### For Contributors

If you want to help make tachyon-engine production-ready:

1. **Clone tachyon-engine repo**
2. **Focus areas**:
   - Complete ASGI 3.0 protocol
   - Middleware system integration
   - Form data parsing
   - Pass tachyon-api test suite

3. **Testing against tachyon-api**:
```bash
# In tachyon-api repo
pip install -e ../tachyon-engine
export TACHYON_ENGINE=tachyon
pytest tests/ -v
```

4. **Success criteria**: All 223 tachyon-api tests must pass

---

## Benchmarking

Once tachyon-engine is functional:

```bash
# Run benchmarks
python benchmarks/tachyon_vs_starlette.py

# Expected results:
# - Path matching: 10x faster
# - Request creation: 2-3x faster
# - JSON response: 1.7x faster
# - Overall: 2-4x faster
```

---

## FAQ

### Why isn't tachyon-engine the default in v1.0.0?

tachyon-engine v0.1.0 has an incomplete ASGI implementation. Rather than delay v1.0.0, we're shipping with:
- ✅ Complete adapter infrastructure
- ✅ Stable Starlette-based implementation
- 🎯 Ready to switch when tachyon-engine is complete

### Will my code break when switching engines?

No. The adapter pattern ensures your Tachyon API code works identically with both engines.

### When will tachyon-engine be production-ready?

Estimated: **Q1 2026** (when v0.2.0+ completes the ASGI protocol)

### Can I help?

Yes! Contributions to [tachyon-engine](https://github.com/jmpanozzoz/tachyon-engine) are welcome.

---

## Roadmap

### v1.0.0 (Current)
- ✅ Adapter infrastructure complete
- ✅ Starlette stable default
- ✅ tachyon-engine experimental support

### v1.1.0 (When tachyon-engine v0.2.0+ ready)
- Switch AUTO mode to prefer tachyon-engine
- Performance benchmarks in README
- Production deployment guides

### v2.0.0 (Future)
- Remove Starlette dependency entirely
- tachyon-engine only
- Pure Rust performance

---

## Technical Details

### Adapter Interface

All engines must implement:

```python
class AsgiApplicationAdapter(ABC):
    def add_route(path, endpoint, methods): ...
    def add_websocket_route(path, endpoint): ...
    def add_middleware(middleware_class, **options): ...
    async def __call__(scope, receive, send): ...
    def get_state(): ...
```

### Current Implementations

1. **StarletteApplicationAdapter** ✅
   - Wraps `starlette.applications.Starlette`
   - 100% feature complete
   - Production-ready

2. **TachyonEngineApplicationAdapter** 🚧
   - Wraps `tachyon_engine.TachyonEngine`
   - Adapter code complete
   - Waiting for engine ASGI implementation

---

## Conclusion

Tachyon API v1.0.0 is **production-ready** with Starlette while being **future-ready** for tachyon-engine's Rust-powered performance gains. The adapter pattern ensures a smooth, zero-downtime transition when the time comes.

**Current recommendation**: Use Starlette (default) for production. Experiment with tachyon-engine in dev environments.
