"""
Tachyon Web Framework

A lightweight, FastAPI-inspired web framework with built-in dependency injection,
automatic parameter validation, and high-performance JSON serialization.

Copyright (C) 2025 Juan Manuel Panozzo Zenere

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License.

For more information, see the documentation and examples.
"""

from .core.app import Tachyon
from .schemas.models import Struct
from .schemas.parameters import Query, Body, Path
from .dependencies.injection import injectable, Depends
from .routing.router import Router
from .features.cache import (
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
    "Tachyon",
    "Struct",
    "Query",
    "Body",
    "Path",
    "injectable",
    "Depends",
    "Router",
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
