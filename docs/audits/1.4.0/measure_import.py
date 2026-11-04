"""Measure import allocations in a fresh process; timings include tracing overhead."""
import json
import platform
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
tracemalloc.start()
start = time.perf_counter()
import tachyon_api  # noqa: E402,F401

current, peak = tracemalloc.get_traced_memory()
from tachyon_api.responses import _caches  # noqa: E402

snapshot = tracemalloc.take_snapshot()
print(json.dumps({
    "python": platform.python_version(),
    "platform": platform.platform(),
    "import_ms_with_tracemalloc": (time.perf_counter() - start) * 1000,
    "traced_current_bytes_after_import": current,
    "traced_peak_bytes_after_import": peak,
    "uvicorn_imported": "uvicorn" in sys.modules,
    "header_cache_shallow_bytes": sum(sys.getsizeof(getattr(_caches, n)) for n in ("_CL_CACHE", "_CL_TUPLE_CACHE")),
    "largest_allocation_sources": [str(stat) for stat in snapshot.statistics("filename")[:6]],
}, indent=2))
