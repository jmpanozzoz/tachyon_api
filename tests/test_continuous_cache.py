"""Cache namespaces, fail-open backends, nonblocking I/O and bounded expiry."""
import asyncio
import importlib
import threading
from collections import OrderedDict

import pytest

from tachyon_api.cache import BaseCacheBackend, CacheConfig, InMemoryCacheBackend, cache


@pytest.mark.parametrize("asynchronous", [False, True])
def test_distinct_closures_have_separate_default_namespaces(asynchronous):
    config = CacheConfig(InMemoryCacheBackend())
    calls = []

    def factory(value):
        if asynchronous:
            @cache(config=config)
            async def calculate():
                calls.append(value)
                return value
        else:
            @cache(config=config)
            def calculate():
                calls.append(value)
                return value
        return calculate

    first, second = factory("first"), factory("second")
    async def exercise():
        assert await first() == "first"
        assert await second() == "second"
        assert await first() == "first"
        assert await second() == "second"
    if asynchronous:
        asyncio.run(exercise())
    else:
        assert (first(), second(), first(), second()) == ("first", "second", "first", "second")
    assert calls == ["first", "second"]


def test_custom_keys_can_share_across_decorations():
    config = CacheConfig(InMemoryCacheBackend(), key_builder=lambda fn, args, kwargs: "shared")
    first = cache(config=config)(lambda: "first")
    second = cache(config=config)(lambda: "second")
    assert first() == second() == "first"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_backend_read_and_write_errors_fail_open_and_log(caplog, asynchronous):
    class BrokenBackend(BaseCacheBackend):
        def get(self, key):
            raise OSError("read unavailable")
        def set(self, key, value, ttl=None):
            raise OSError("write unavailable")
    if asynchronous:
        @cache(backend=BrokenBackend())
        async def calculate():
            return 42
        assert asyncio.run(calculate()) == 42
    else:
        @cache(backend=BrokenBackend())
        def calculate():
            return 42
        assert calculate() == 42
    assert "Cache get failed" in caplog.text and "read unavailable" in caplog.text
    assert "Cache set failed" in caplog.text and "write unavailable" in caplog.text


@pytest.mark.asyncio
async def test_external_backend_does_not_block_event_loop():
    loop_thread = threading.get_ident()
    started = threading.Event()
    release = threading.Event()
    worker_threads = []
    class BlockingBackend(BaseCacheBackend):
        def get(self, key):
            worker_threads.append(threading.get_ident())
            started.set()
            assert release.wait(2), "event loop could not release blocking backend"
            return None
        def set(self, key, value, ttl=None):
            worker_threads.append(threading.get_ident())

    @cache(backend=BlockingBackend())
    async def calculate():
        return 42

    task = asyncio.create_task(calculate())
    try:
        async def release_backend():
            while not started.is_set():
                await asyncio.sleep(0)
            release.set()
        await asyncio.wait_for(release_backend(), timeout=3)
        assert await asyncio.wait_for(task, timeout=3) == 42
    finally:
        release.set()
        await task
    assert len(worker_threads) == 2 and all(worker != loop_thread for worker in worker_threads)


@pytest.mark.asyncio
async def test_only_builtin_memory_backend_runs_inline(monkeypatch):
    module = importlib.import_module("tachyon_api.cache")
    async def forbidden(*args, **kwargs):
        raise AssertionError("built-in memory cache must remain inline")
    monkeypatch.setattr(module, "run_in_threadpool", forbidden)
    @cache(backend=InMemoryCacheBackend())
    async def calculate():
        return 7
    assert await calculate() == await calculate() == 7


def test_memory_cache_lazy_expiry_capacity_and_no_write_sweep(monkeypatch):
    module = importlib.import_module("tachyon_api.cache")
    clock = [10.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    class NoScanStore(OrderedDict):
        def items(self):
            raise AssertionError("writes must not scan stored entries")
    backend = InMemoryCacheBackend(max_entries=2)
    backend._store = NoScanStore()
    backend.set("old", "old", ttl=1)
    backend.set("live", "live", ttl=10)
    clock[0] = 12.0
    assert backend.get("old") is None
    backend.set("new", "new", ttl=10)
    assert backend.get("live") == "live"
    backend.set("last", "last", ttl=10)
    assert backend.get("new") is None
    assert len(backend._store) == 2
    clock[0] = 30.0
    assert backend.get("live") is None and backend.get("last") is None


def test_async_backend_methods_rejected_at_decoration():
    class AsyncBackend(BaseCacheBackend):
        async def get(self, key):
            return None
        async def set(self, key, value, ttl=None):
            pass
    with pytest.raises(TypeError, match="synchronous"):
        cache(backend=AsyncBackend())(lambda: 1)


@pytest.mark.parametrize("ttl,expected", [(0.01, 1), (0.5, 1), (1.25, 2), (2.0, 2)])
def test_external_adapters_round_positive_ttl_up_without_disabling_expiration(ttl, expected):
    from tachyon_api.cache import MemcachedCacheBackend, RedisCacheBackend

    class RedisClient:
        def set(self, key, value, *, ex=None):
            assert ex is None or ex > 0, "Redis rejects zero expiration"
            self.expiration = ex

    class MemcachedClient:
        def set(self, key, value, *, expire):
            self.expiration = expire

    class BinaryMemcachedClient:
        def set(self, key, value, *, time):
            self.expiration = time

    for backend_type, client in [
        (RedisCacheBackend, RedisClient()),
        (MemcachedCacheBackend, MemcachedClient()),
        (MemcachedCacheBackend, BinaryMemcachedClient()),
    ]:
        backend_type(client).set("key", "value", ttl=ttl)
        assert client.expiration == expected
        assert client.expiration >= ttl


@pytest.mark.parametrize("ttl", [None, 0, -1])
def test_external_adapters_preserve_explicit_no_expiration(ttl):
    from tachyon_api.cache import MemcachedCacheBackend, RedisCacheBackend

    class Client:
        def set(self, key, value, **kwargs):
            self.options = kwargs

    redis_client, memcached_client = Client(), Client()
    RedisCacheBackend(redis_client).set("key", "value", ttl=ttl)
    MemcachedCacheBackend(memcached_client).set("key", "value", ttl=ttl)
    assert redis_client.options == {}
    assert memcached_client.options == {"expire": 0}


@pytest.mark.parametrize("ttl", [2592000, 2592000.01, 2592001, 60 * 24 * 60 * 60])
@pytest.mark.parametrize("binary_client", [False, True])
def test_memcached_long_ttl_uses_absolute_expiration(monkeypatch, ttl, binary_client):
    import math
    from tachyon_api.cache import MemcachedCacheBackend

    module = importlib.import_module("tachyon_api.cache")
    now = 1_800_000_000.75
    monkeypatch.setattr(module.time, "time", lambda: now)

    class MemcachedClient:
        def set(self, key, value, *, expire):
            self.expiration = expire

    class BinaryMemcachedClient:
        def set(self, key, value, *, time):
            self.expiration = time

    client = BinaryMemcachedClient() if binary_client else MemcachedClient()
    MemcachedCacheBackend(client).set("key", "value", ttl=ttl)
    if ttl == 2592000:
        assert client.expiration == ttl  # The boundary still means relative seconds.
    else:
        assert client.expiration == math.ceil(now + ttl)
        assert 0 <= client.expiration - now - ttl < 1
