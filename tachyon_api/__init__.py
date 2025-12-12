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

from .app import Tachyon
from .models import Struct
from .params import Query, Body, Path, Header, Cookie, Form, File
from .files import UploadFile
from .di import injectable, Depends
from .router import Router
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
    "Tachyon",
    "Struct",
    "Query",
    "Body",
    "Path",
    "Header",
    "Cookie",
    "Form",
    "File",
    "UploadFile",
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
