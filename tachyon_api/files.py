"""
Tachyon Web Framework - File Upload Module

This module provides classes for handling file uploads in a FastAPI-compatible way.
It wraps Starlette's file handling functionality.
"""

from starlette.datastructures import UploadFile as StarletteUploadFile

# Re-export Starlette's UploadFile for use in Tachyon
# This provides a familiar API for users coming from FastAPI
UploadFile = StarletteUploadFile

__all__ = ["UploadFile"]
