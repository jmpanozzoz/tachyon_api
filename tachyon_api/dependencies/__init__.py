"""
Tachyon API dependency injection system.
"""

from .injection import injectable, Depends, _registry
from .resolver import DependencyResolver

__all__ = ["injectable", "Depends", "_registry", "DependencyResolver"]
