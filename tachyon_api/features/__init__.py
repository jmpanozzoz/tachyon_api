"""
Tachyon API features and extensions.
"""

try:
    from .cache import (
        cache,
        CacheConfig,
        create_cache_config,
        set_cache_config,
        get_cache_config,
        InMemoryCacheBackend,
        BaseCacheBackend,
        RedisCacheBackend,
        MemcachedCacheBackend,
    )

    __all__ = [
        "cache",
        "CacheConfig",
        "create_cache_config",
        "set_cache_config",
        "get_cache_config",
        "InMemoryCacheBackend",
        "BaseCacheBackend",
        "RedisCacheBackend",
        "MemcachedCacheBackend",
    ]
except ImportError:
    __all__ = []
