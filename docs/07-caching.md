# 7. Caching

`cache` supports synchronous and asynchronous functions. The first parameter
is named `TTL` (uppercase), in seconds. A missing TTL uses `default_ttl`;
zero and negative values mean no expiration. `None` results are cache misses.

```python
from tachyon_api import Tachyon, cache, create_cache_config
from tachyon_api.cache import CacheConfig, InMemoryCacheBackend

config = CacheConfig(InMemoryCacheBackend(max_entries=1024), default_ttl=60)
app = Tachyon(cache_config=config)

@app.get("/users/{user_id}")
@cache(TTL=120, config=config)
async def user(user_id: int):
    return {"id": user_id}
```

`create_cache_config(backend=None, default_ttl=60, key_builder=None,
enabled=True)` creates and installs a process-global config. `set_cache_config`
replaces that global. Without `config=`, each decorator captures the current
config object, backend, TTL and key builder at decoration time. Replacing the
global later does not rebind existing decorators; mutating the captured
`enabled` field takes effect. `Tachyon(cache_config=...)` also sets that global;
it does not bind decorators to an app. Use explicit `config=` for independent
apps in the same process. Config changes should happen during setup.

The in-memory backend uses a monotonic clock, protects operations with a lock,
and defaults to at most 1024 entries. Reads remove expired entries on access; capacity evicts the least recently used entry. Expired entries not accessed may remain within that bounded capacity. Its operations are thread safe, but
concurrent misses may compute the same function more than once. Values are
stored by reference and should be treated as immutable.

Custom key builders receive `(function, args, kwargs)`. `unless` receives
`(args, kwargs)` and skips caching when true:

```python
@cache(TTL=30, config=config,
       key_builder=lambda func, args, kwargs: f"user:{kwargs['user_id']}",
       unless=lambda args, kwargs: kwargs.get("user_id") == 0)
async def cached_user(*, user_id: int):
    return {"id": user_id}
```

Default keys include a random namespace per decoration and argument representations. Distinct closures or app wrappers therefore do not share keys even when module and qualname match. The default namespace changes across workers and restarts: use a custom stable `key_builder` when shared external cache reuse is intentional.
Request objects and dependencies can affect those representations. Only cache
responses whose authorization, tenant and user context are included in the key.

Invalidation uses synchronous backend methods:

```python
config.backend.delete("user:123")
config.backend.clear()
```

Redis and Memcached adapters take an existing synchronous client:

```python
from tachyon_api.cache import RedisCacheBackend, MemcachedCacheBackend

redis_backend = RedisCacheBackend(redis_client)
memcached_backend = MemcachedCacheBackend(memcached_client)
```

Install/configure those clients separately. Positive fractional TTLs round up to whole seconds in these adapters; external expiration has approximately one-second resolution. Memcached durations above 30 days are translated to an absolute Unix expiration timestamp, as required by the [Memcached protocol](https://docs.memcached.org/protocols/basic/). Adapters do not serialize arbitrary
Python results: supply values the client supports and matching serialization.
Redis `clear()` calls `flushdb()` on the selected database only; it never falls
back to `flushall()`. Use a dedicated database because `flushdb()` also removes
other keys in that database. Memcached `clear()` flushes the selected server.
Cache read/write failures are logged and fail open: the decorated function still computes its result. The adapter interface accepts synchronous clients only; do not pass an async client. Clients must support concurrent calls. Async decorated functions offload external backend get/set operations to the Starlette thread pool; the exact built-in in-memory backend stays inline. Direct adapter calls, delete and clear remain synchronous, so offload those explicitly when used from async code.
