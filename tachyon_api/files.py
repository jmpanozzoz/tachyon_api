"""
Tachyon Web Framework - File Upload Module

This module provides classes for handling file uploads in a FastAPI-compatible way.
It wraps Starlette's file handling functionality.
"""

import os

from starlette.datastructures import UploadFile as StarletteUploadFile


class UploadFile(StarletteUploadFile):
    """UploadFile with filename sanitization against path traversal attacks.

    The `filename` attribute is stripped of directory components and null bytes
    at construction time. If the original name was ``../../../etc/passwd``, the
    sanitized value will be ``passwd``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.filename is not None:
            # Strip null bytes then any directory prefix
            self.filename = os.path.basename(self.filename.replace("\x00", ""))


__all__ = ["UploadFile"]
