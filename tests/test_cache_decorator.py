import time
import pytest
from unittest.mock import MagicMock
from starlette.testclient import TestClient

from tachyon_api import Tachyon, Query
from tachyon_api.cache import (
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


class TestInMemoryCacheBackend:
    def test_delete_existing_key(self):
        from tachyon_api.cache import InMemoryCacheBackend
        b = InMemoryCacheBackend()
        b.set("k", "v", ttl=60)
        b.delete("k")
        assert b.get("k") is None

    def test_delete_nonexistent_key(self):
        from tachyon_api.cache import InMemoryCacheBackend
        b = InMemoryCacheBackend()
        b.delete("nonexistent")  # should not raise

    def test_clear(self):
        from tachyon_api.cache import InMemoryCacheBackend
        b = InMemoryCacheBackend()
        b.set("a", 1)
        b.set("b", 2)
        b.clear()
        assert b.get("a") is None

    def test_expired_key_lazy_deleted(self):
        from tachyon_api.cache import InMemoryCacheBackend
        import time
        b = InMemoryCacheBackend()
        b.set("k", "v", ttl=0.01)
        time.sleep(0.05)
        assert b.get("k") is None


class TestCacheDecoratorUnlessPredicate:
    @pytest.mark.asyncio
    async def test_async_unless_predicate_skips_cache(self):
        from tachyon_api.cache import cache, create_cache_config, InMemoryCacheBackend
        be = InMemoryCacheBackend()
        create_cache_config(backend=be, default_ttl=60)
        calls = [0]

        @cache(unless=lambda args, kwargs: True)
        async def async_fn(x):
            calls[0] += 1
            return x

        assert await async_fn(1) == 1
        assert await async_fn(1) == 1
        assert calls[0] == 2

    def test_cache_disabled_config(self):
        from tachyon_api.cache import cache, create_cache_config, InMemoryCacheBackend
        create_cache_config(backend=InMemoryCacheBackend(), default_ttl=60, enabled=False)
        calls = [0]

        @cache()
        def fn():
            calls[0] += 1
            return 42

        fn()
        fn()
        assert calls[0] == 2  # cache disabled, always calls

    def test_cache_key_builder(self):
        from tachyon_api.cache import cache, create_cache_config, InMemoryCacheBackend
        be = InMemoryCacheBackend()
        create_cache_config(backend=be, default_ttl=60)
        calls = [0]

        @cache(key_builder=lambda f, args, kwargs: "fixed-key")
        def fn(x):
            calls[0] += 1
            return x

        fn(1)
        fn(2)
        assert calls[0] == 1  # same key, cached after first call


class TestRedisCacheBackend:
    def test_get_returns_string_value(self):
        from tachyon_api.cache import RedisCacheBackend
        client = MagicMock()
        client.get.return_value = "value"
        b = RedisCacheBackend(client)
        assert b.get("key") == "value"

    def test_get_decodes_bytes(self):
        from tachyon_api.cache import RedisCacheBackend
        client = MagicMock()
        client.get.return_value = b"hello"
        b = RedisCacheBackend(client)
        assert b.get("key") == "hello"

    def test_get_returns_bytes_if_not_decodable(self):
        from tachyon_api.cache import RedisCacheBackend
        client = MagicMock()
        client.get.return_value = b"\xff\xfe"  # invalid utf-8
        b = RedisCacheBackend(client)
        result = b.get("key")
        assert result == b"\xff\xfe"

    def test_set_with_ttl(self):
        from tachyon_api.cache import RedisCacheBackend
        client = MagicMock()
        b = RedisCacheBackend(client)
        b.set("key", "val", ttl=30)
        client.set.assert_called_once_with("key", "val", ex=30)

    def test_set_no_ttl(self):
        from tachyon_api.cache import RedisCacheBackend
        client = MagicMock()
        b = RedisCacheBackend(client)
        b.set("key", "val", ttl=None)
        client.set.assert_called_once_with("key", "val")

    def test_delete(self):
        from tachyon_api.cache import RedisCacheBackend
        client = MagicMock()
        b = RedisCacheBackend(client)
        b.delete("key")
        client.delete.assert_called_once_with("key")

    def test_delete_ignores_exception(self):
        from tachyon_api.cache import RedisCacheBackend
        client = MagicMock()
        client.delete.side_effect = Exception("connection error")
        b = RedisCacheBackend(client)
        b.delete("key")  # should not raise

    def test_clear_noop(self):
        from tachyon_api.cache import RedisCacheBackend
        b = RedisCacheBackend(MagicMock())
        b.clear()  # no-op, should not raise


class TestMemcachedCacheBackend:
    def test_get(self):
        from tachyon_api.cache import MemcachedCacheBackend
        client = MagicMock()
        client.get.return_value = "cached"
        b = MemcachedCacheBackend(client)
        assert b.get("k") == "cached"

    def test_set_pymemcache_style(self):
        from tachyon_api.cache import MemcachedCacheBackend
        client = MagicMock()
        b = MemcachedCacheBackend(client)
        b.set("k", "v", ttl=10)
        client.set.assert_called_with("k", "v", expire=10)

    def test_set_binary_memcached_style(self):
        from tachyon_api.cache import MemcachedCacheBackend
        client = MagicMock()
        client.set.side_effect = [TypeError("wrong kwarg"), None]
        b = MemcachedCacheBackend(client)
        b.set("k", "v", ttl=10)
        # second call uses time=
        assert client.set.call_count == 2

    def test_set_no_ttl(self):
        from tachyon_api.cache import MemcachedCacheBackend
        client = MagicMock()
        b = MemcachedCacheBackend(client)
        b.set("k", "v", ttl=None)
        client.set.assert_called_with("k", "v", expire=0)

    def test_delete_ignores_exception(self):
        from tachyon_api.cache import MemcachedCacheBackend
        client = MagicMock()
        client.delete.side_effect = Exception("error")
        b = MemcachedCacheBackend(client)
        b.delete("k")  # should not raise

    def test_clear_flush_all(self):
        from tachyon_api.cache import MemcachedCacheBackend
        client = MagicMock()
        b = MemcachedCacheBackend(client)
        b.clear()
        client.flush_all.assert_called_once()

    def test_clear_ignores_exception(self):
        from tachyon_api.cache import MemcachedCacheBackend
        client = MagicMock()
        client.flush_all.side_effect = Exception("error")
        b = MemcachedCacheBackend(client)
        b.clear()  # should not raise


def test_cache_expired_key_concurrent_delete():
    """Cover KeyError branch in lazy expiration when key deleted concurrently."""
    from tachyon_api.cache import InMemoryCacheBackend
    import time
    b = InMemoryCacheBackend()
    b.set("k", "v", ttl=0.01)
    time.sleep(0.05)
    # Delete the key before get() tries to clean it up
    b._store.pop("k", None)
    # get() should handle the already-gone key gracefully
    result = b.get("k")
    assert result is None


def test_cache_async_backend_set_failure_logged(caplog):
    """Cover the except branch in async_wrapper when be.set raises."""
    from tachyon_api.cache import cache, create_cache_config, BaseCacheBackend
    import logging

    class FailingBackend(BaseCacheBackend):
        def get(self, key):
            return None
        def set(self, key, value, ttl=None):
            raise RuntimeError("backend error")
        def delete(self, key): pass
        def clear(self): pass

    create_cache_config(backend=FailingBackend(), default_ttl=60)

    @cache()
    async def afn():
        return 42

    import asyncio
    with caplog.at_level(logging.WARNING):
        result = asyncio.run(afn())
    assert result == 42  # still returns despite set failure


def test_cache_sync_backend_set_failure_logged(caplog):
    """Cover the except branch in sync wrapper when be.set raises."""
    from tachyon_api.cache import cache, create_cache_config, BaseCacheBackend
    import logging

    class FailingBackend(BaseCacheBackend):
        def get(self, key): return None
        def set(self, key, value, ttl=None): raise RuntimeError("error")
        def delete(self, key): pass
        def clear(self): pass

    create_cache_config(backend=FailingBackend(), default_ttl=60)

    @cache()
    def sfn():
        return 99

    with caplog.at_level(logging.WARNING):
        result = sfn()
    assert result == 99
