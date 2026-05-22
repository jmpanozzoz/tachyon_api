"""Dependency injection resolution pipeline."""

from ._resolver import DependencyResolver
from ._sig_cache import _SIG_CACHE  # re-exported for internal callers

__all__ = ["DependencyResolver", "_SIG_CACHE"]
