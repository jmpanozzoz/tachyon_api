"""
Tachyon Web Framework - File Upload Module

This module provides classes for handling file uploads in a FastAPI-compatible way.
It wraps Starlette's file handling functionality.
"""

import inspect
import ntpath

from starlette.datastructures import UploadFile as StarletteUploadFile
from .utils.type_utils import TypeUtils


def _safe_filename(filename):
    if filename is None:
        return None
    # ntpath handles Windows drives and both separator styles on every host.
    name = ntpath.basename(filename.replace("\x00", "")).rsplit(":", 1)[-1]
    return "" if name in (".", "..") else name


class UploadFile(StarletteUploadFile):
    """UploadFile with filename sanitization against path traversal attacks.

    The `filename` attribute is stripped of directory components and null bytes
    at construction time, with Unix and Windows paths recognized on every OS.
    Applications must still choose a storage location and collision policy.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filename = _safe_filename(self.filename)

    @classmethod
    def from_starlette(cls, upload):
        """Adapt metadata without reading, copying or taking a second stream."""
        if isinstance(upload, cls):
            upload.filename = _safe_filename(upload.filename)
            return upload
        return cls(upload.file, size=upload.size, filename=upload.filename, headers=upload.headers)


def validate_file_parameter(annotation, default):
    """Validate the supported File contract once during route registration."""
    base, _ = TypeUtils.unwrap_optional(annotation)
    is_list, item = TypeUtils.is_list_type(base)
    supported = (UploadFile, StarletteUploadFile)
    if (is_list and item not in supported) or (
        not is_list and base not in (*supported, inspect.Parameter.empty)
    ):
        raise TypeError("File parameters require UploadFile or list[UploadFile] annotations")
    if default is ... or default is None:
        return
    if is_list and isinstance(default, list) and not default:
        return
    raise TypeError("File defaults must be None, an empty upload list, or ...")


__all__ = ["UploadFile"]
