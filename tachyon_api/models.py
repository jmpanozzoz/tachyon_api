"""
Tachyon Web Framework - Data Models Module

This module provides the base model class for request/response data validation
using msgspec for high-performance JSON serialization and validation.
"""

from msgspec import Struct, Meta

__all__ = ["Struct", "Meta"]
