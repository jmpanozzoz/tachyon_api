import time
from starlette.testclient import TestClient

from tachyon_api import Tachyon, Query
from tachyon_api.features.cache import (
    cache,
    create_cache_config,
    InMemoryCacheBackend,
    CacheConfig,
)


def test_cache_decorator_caches_sync_function_results():
    calls = {"count": 0}

    @cache(TTL=0.2)
    def add(a, b):
        calls["count"] += 1
        return a + b

    # First call computes and caches
    assert add(1, 2) == 3
    assert calls["count"] == 1
    # Second call within TTL should use cache
    assert add(1, 2) == 3
    assert calls["count"] == 1
    # Different args should compute again
    assert add(2, 2) == 4
    assert calls["count"] == 2

    # After TTL expires, should recompute
    time.sleep(0.25)
    assert add(1, 2) == 3
    assert calls["count"] == 3


def test_cache_decorator_works_for_routes_and_keys_include_params():
    app = Tachyon()

    counter = {"value": 0}

    @app.get("/items/{item_id}")
    @cache(TTL=0.5)
    def get_item(item_id: int, q: str = Query(None)):
        counter["value"] += 1
        return {"item_id": item_id, "q": q, "call": counter["value"]}

    client = TestClient(app._router)

    # First call computes
    r1 = client.get("/items/1?q=foo").json()
    # Second call within TTL should be cached (same call index)
    r2 = client.get("/items/1?q=foo").json()
    assert r1 == r2
    assert r1["call"] == 1

    # Different query param should not hit cache
    r3 = client.get("/items/1?q=bar").json()
    assert r3["call"] == 2

    # Different path param should not hit cache
    r4 = client.get("/items/2?q=foo").json()
    assert r4["call"] == 3


def test_cache_decorator_supports_async_route_functions():
    app = Tachyon()

    calls = {"count": 0}

    @app.get("/async")
    @cache(TTL=0.5)
    async def async_handler(x: int = 1):
        calls["count"] += 1
        return {"x": x, "calls": calls["count"]}

    client = TestClient(app._router)

    r1 = client.get("/async?x=5").json()
    r2 = client.get("/async?x=5").json()
    assert r1 == r2
    assert r1["calls"] == 1


class DummyBackend(InMemoryCacheBackend):
    def __init__(self):
        super().__init__()
        self.set_calls = 0
        self.get_calls = 0

    def get(self, key):
        self.get_calls += 1
        return super().get(key)

    def set(self, key, value, ttl: float | None = None):
        self.set_calls += 1
        return super().set(key, value, ttl)


def test_cache_global_config_and_backend_integration():
    backend = DummyBackend()
    cfg: CacheConfig = create_cache_config(backend=backend, default_ttl=0.5)

    app = Tachyon(cache_config=cfg)

    calls = {"count": 0}

    @app.get("/conf")
    @cache()  # No TTL specified -> uses default_ttl from config
    def conf():
        calls["count"] += 1
        return {"calls": calls["count"]}

    client = TestClient(app._router)
    client.get("/conf")
    client.get("/conf")

    # Should have cached and only called set/get minimally
    assert calls["count"] == 1
    assert backend.set_calls >= 1
    assert backend.get_calls >= 1


def test_cache_key_builder_customization_and_unless_predicate():
    backend = InMemoryCacheBackend()
    create_cache_config(backend=backend, default_ttl=1)

    calls = {"count": 0}

    # Only cache if x is even
    @cache(TTL=0.5, unless=lambda args, kwargs: kwargs.get("x", 0) % 2 == 1)
    def f(x: int):
        calls["count"] += 1
        return x * 2

    assert f(2) == 4
    assert f(2) == 4  # cached
    assert f(3) == 6  # not cached due to predicate
    assert calls["count"] == 2
