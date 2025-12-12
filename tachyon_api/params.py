"""
Tachyon Web Framework - Parameter Definition Module

This module provides parameter marker classes for defining how endpoint function
parameters should be resolved from HTTP requests (query strings, path variables,
and request bodies).
"""

from typing import Any, Optional


class Query:
    """
    Marker class for query string parameters.

    Use this to define parameters that should be extracted from the URL query string
    with optional default values and automatic type conversion.

    Args:
        default: Default value if parameter is not provided. Use ... for required parameters.
        description: Optional description for OpenAPI documentation.

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

    def __init__(self, default: Any = ..., description: Optional[str] = None):
        """
        Initialize a Query parameter marker.

        Args:
            default: Default value for the parameter. Use ... (Ellipsis) for required parameters.
            description: Optional description for API documentation.
        """
        self.default = default
        self.description = description


class Path:
    """
    Marker class for path parameters.

    Use this to define parameters that should be extracted from the URL path.
    Path parameters are always required.

    Args:
        description: Optional description for OpenAPI documentation.
    """

    def __init__(self, description: Optional[str] = None):
        """
        Initialize a Path parameter marker.

        Args:
            description: Optional description for API documentation.
        """
        self.description = description


class Body:
    """
    Marker class for request body parameters.

    Use this to define parameters that should be extracted and validated from
    the JSON request body. The parameter type should be a Struct subclass.

    Args:
        description: Optional description for OpenAPI documentation.
    """

    def __init__(self, description: Optional[str] = None):
        """
        Initialize a Body parameter marker.

        Args:
            description: Optional description for API documentation.
        """
        self.description = description


class Header:
    """
    Marker class for HTTP header parameters.

    Use this to define parameters that should be extracted from HTTP request headers.
    Header names are case-insensitive per HTTP specification.

    Args:
        default: Default value if header is not provided. Use ... for required headers.
        alias: Optional custom header name. If not provided, the parameter name is used
               with underscores converted to hyphens.
        description: Optional description for OpenAPI documentation.

    Example:
        @app.get("/protected")
        def protected(
            authorization: str = Header(...),              # Required header
            x_request_id: str = Header("default-id"),      # Optional with default
            token: str = Header(..., alias="X-Auth-Token") # Custom header name
        ):
            return {"auth": authorization, "id": x_request_id}

    Note:
        - Header names are matched case-insensitively
        - Parameter names with underscores match headers with hyphens
          (e.g., x_request_id matches X-Request-Id)
        - Missing required headers return 422 Unprocessable Entity
    """

    def __init__(
        self,
        default: Any = ...,
        alias: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        Initialize a Header parameter marker.

        Args:
            default: Default value for the header. Use ... (Ellipsis) for required.
            alias: Optional custom header name to use instead of parameter name.
            description: Optional description for API documentation.
        """
        self.default = default
        self.alias = alias
        self.description = description


class Cookie:
    """
    Marker class for HTTP cookie parameters.

    Use this to define parameters that should be extracted from HTTP cookies.

    Args:
        default: Default value if cookie is not provided. Use ... for required cookies.
        alias: Optional custom cookie name.
        description: Optional description for OpenAPI documentation.

    Example:
        @app.get("/profile")
        def profile(session_id: str = Cookie(...)):
            return {"session": session_id}

    Note:
        - Missing required cookies return 422 Unprocessable Entity
    """

    def __init__(
        self,
        default: Any = ...,
        alias: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        Initialize a Cookie parameter marker.

        Args:
            default: Default value for the cookie. Use ... (Ellipsis) for required.
            alias: Optional custom cookie name to use instead of parameter name.
            description: Optional description for API documentation.
        """
        self.default = default
        self.alias = alias
        self.description = description


class Form:
    """
    Marker class for form data parameters.

    Use this to define parameters that should be extracted from
    application/x-www-form-urlencoded or multipart/form-data request bodies.

    Args:
        default: Default value if field is not provided. Use ... for required fields.
        alias: Optional custom field name.
        description: Optional description for OpenAPI documentation.

    Example:
        @app.post("/login")
        async def login(
            username: str = Form(...),
            password: str = Form(...),
        ):
            return {"username": username}

    Note:
        - Missing required form fields return 422 Unprocessable Entity
        - Works with multipart/form-data for file uploads
    """

    def __init__(
        self,
        default: Any = ...,
        alias: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        Initialize a Form parameter marker.

        Args:
            default: Default value for the field. Use ... (Ellipsis) for required.
            alias: Optional custom field name to use instead of parameter name.
            description: Optional description for API documentation.
        """
        self.default = default
        self.alias = alias
        self.description = description


class File:
    """
    Marker class for file upload parameters.

    Use this to define parameters that should be extracted from
    multipart/form-data file uploads. The parameter type should be UploadFile.

    Args:
        default: Default value if file is not provided. Use ... for required files,
                 None for optional files.
        description: Optional description for OpenAPI documentation.

    Example:
        from tachyon_api.files import UploadFile

        @app.post("/upload")
        async def upload(file: UploadFile = File(...)):
            content = await file.read()
            return {"filename": file.filename, "size": len(content)}

        @app.post("/optional-upload")
        async def optional(file: UploadFile = File(None)):
            if file is None:
                return {"uploaded": False}
            return {"uploaded": True, "filename": file.filename}

    Note:
        - Missing required files return 422 Unprocessable Entity
        - Use UploadFile type annotation for file parameters
    """

    def __init__(
        self,
        default: Any = ...,
        description: Optional[str] = None,
    ):
        """
        Initialize a File parameter marker.

        Args:
            default: Default value. Use ... for required, None for optional.
            description: Optional description for API documentation.
        """
        self.default = default
        self.description = description
