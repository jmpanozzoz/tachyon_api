"""
Core functionality for Tachyon API.

This module contains the core components of the framework:
- lifecycle: Application startup/shutdown event handling
"""

from .lifecycle import LifecycleManager

__all__ = ["LifecycleManager"]
