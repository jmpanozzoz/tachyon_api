"""
Tachyon Web Framework

A lightweight, FastAPI-inspired web framework with built-in dependency injection,
automatic parameter validation, and high-performance JSON serialization.

For more information, see the documentation and examples.
"""

from .app import Tachyon
from .models import Struct
from .params import Query, Body, Path
from .di import injectable, Depends
from .openapi import OpenAPIConfig

__all__ = [
    "Tachyon",
    "Struct",
    "Query",
    "Body",
    "Path",
    "injectable",
    "Depends",
    "OpenAPIConfig",
]
