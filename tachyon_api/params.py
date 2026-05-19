"""Parameter marker classes: Query, Path, Body, Header, Cookie, Form, File."""

from typing import Any, Optional


class Query:
    """Marks a parameter as coming from the URL query string. Use `...` for required."""

    def __init__(self, default: Any = ..., description: Optional[str] = None):
        self.default = default
        self.description = description


class Path:
    """Marks a parameter as coming from the URL path segment."""

    def __init__(self, description: Optional[str] = None):
        self.description = description


class Body:
    """Marks a parameter as coming from the JSON request body (must be a Struct subclass)."""

    def __init__(self, description: Optional[str] = None):
        self.description = description


class Header:
    """Marks a parameter as coming from an HTTP header. Underscores in name map to hyphens."""

    def __init__(
        self,
        default: Any = ...,
        alias: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.default = default
        self.alias = alias
        self.description = description


class Cookie:
    """Marks a parameter as coming from an HTTP cookie."""

    def __init__(
        self,
        default: Any = ...,
        alias: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.default = default
        self.alias = alias
        self.description = description


class Form:
    """Marks a parameter as coming from form data (urlencoded or multipart)."""

    def __init__(
        self,
        default: Any = ...,
        alias: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.default = default
        self.alias = alias
        self.description = description


class File:
    """Marks a parameter as a file upload (multipart/form-data). Use UploadFile as type."""

    def __init__(
        self,
        default: Any = ...,
        description: Optional[str] = None,
    ):
        self.default = default
        self.description = description
