"""
Tachyon Web Framework - Parameter Definition Module

This module provides parameter marker classes for defining how endpoint function
parameters should be resolved from HTTP requests (query strings, path variables,
and request bodies).
"""

from typing import Any, Union


class Query:
    """
    Marker class for query string parameters.

    Use this to define parameters that should be extracted from the URL query string
    with optional default values and automatic type conversion.

    Args:
        default: Default value if parameter is not provided. Use ... for required parameters.

    Example:
        @app.get("/search")
        def search(
            q: str = Query(...),        # Required query parameter
            limit: int = Query(10),     # Optional with default value
            active: bool = Query(False) # Optional boolean parameter
        ):
            return {"query": q, "limit": limit, "active": active}

    Note:
        - Boolean parameters accept: "true", "1", "t", "yes" (case-insensitive) as True
        - Type conversion is automatic based on parameter annotation
        - Missing required parameters return 422 Unprocessable Entity
        - Invalid type conversions return 422 Unprocessable Entity
    """

    def __init__(self, default: Any = ...):
        """
        Initialize a query parameter definition.

        Args:
            default: The default value to use if parameter is not provided.
                    Use ... (Ellipsis) to mark as required parameter.
        """
        self.default = default


class Body:
    """
    Marker class for request body parameters.

    Use this to define parameters that should be extracted and validated from
    the JSON request body using Struct models for automatic validation.

    Example:
        class UserModel(Struct):
            name: str
            email: str
            age: int

        @app.post("/users")
        def create_user(user: UserModel = Body()):
            return {"created": user.name, "email": user.email}

    Note:
        - Only works with Struct-based models for validation
        - Automatically validates JSON structure and types
        - Invalid JSON or validation errors return 422 Unprocessable Entity
        - Uses msgspec for high-performance JSON parsing and validation
    """

    def __init__(self):
        """Initialize a body parameter definition."""
        pass


class Path:
    """
    Marker class for explicit path parameters.

    Use this to explicitly mark parameters that should be extracted from
    the URL path variables with automatic type conversion.

    Example:
        @app.get("/users/{user_id}")
        def get_user(user_id: int = Path()):
            return {"user_id": user_id, "type": type(user_id).__name__}

        # Alternative implicit syntax (also supported):
        @app.get("/users/{user_id}")
        def get_user(user_id: int):  # No Path() needed
            return {"user_id": user_id}

    Note:
        - Type conversion is automatic based on parameter annotation
        - Invalid type conversions return 404 Not Found
        - Missing path parameters return 404 Not Found
        - Both explicit Path() and implicit syntax are supported
    """

    def __init__(self):
        """Initialize a path parameter definition."""
        pass
