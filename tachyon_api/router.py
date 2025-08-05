"""
Tachyon Router Module

Provides route grouping functionality similar to FastAPI's APIRouter,
allowing for better organization of routes with common prefixes, tags, and dependencies.
"""

from functools import partial
from typing import List, Optional, Any, Callable, Dict

from .di import Depends


class Router:
    """
    Router class for grouping related routes with common configuration.

    Similar to FastAPI's APIRouter, allows grouping routes with:
    - Common prefixes
    - Common tags
    - Common dependencies
    - Better organization of related endpoints

    Note: Router stores route definitions but doesn't implement the actual routing logic.
    The routing logic is handled by the main Tachyon app when the router is included.
    """

    def __init__(
        self,
        prefix: str = "",
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[Depends]] = None,
        responses: Optional[Dict[int, Dict[str, Any]]] = None,
    ):
        """
        Initialize a new Router instance.

        Args:
            prefix: Common prefix for all routes in this router
            tags: List of tags to apply to all routes
            dependencies: List of dependencies to apply to all routes
            responses: Common responses for OpenAPI documentation
        """
        # Normalize prefix - ensure it starts with / if not empty
        if prefix and not prefix.startswith("/"):
            prefix = "/" + prefix
        elif prefix is None:
            prefix = ""

        self.prefix = prefix
        self.tags = tags or []
        self.dependencies = dependencies or []
        self.responses = responses or {}
        self.routes: List[Dict[str, Any]] = []

        # Create HTTP method decorators using the same pattern as Tachyon
        http_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
        for method in http_methods:
            setattr(
                self,
                method.lower(),
                partial(self._create_route_decorator, http_method=method),
            )

    def _create_route_decorator(self, path: str, *, http_method: str, **kwargs):
        """
        Create a decorator for the specified HTTP method.

        This method is similar to Tachyon's _create_decorator but stores routes
        instead of registering them immediately.

        Args:
            path: URL path pattern (will be prefixed with router prefix)
            http_method: HTTP method name (GET, POST, PUT, DELETE, etc.)
            **kwargs: Additional route options (summary, description, tags, etc.)

        Returns:
            A decorator function that stores the endpoint with the router
        """

        def decorator(endpoint_func: Callable):
            # Combine router tags with route-specific tags
            route_tags = list(self.tags)  # Start with router tags
            if "tags" in kwargs:
                if isinstance(kwargs["tags"], list):
                    route_tags.extend(kwargs["tags"])
                else:
                    route_tags.append(kwargs["tags"])

            # Update kwargs with combined tags
            if route_tags:
                kwargs["tags"] = route_tags

            # Store the route information for later registration
            route_info = {
                "path": path,
                "method": http_method,
                "func": endpoint_func,
                "dependencies": self.dependencies.copy(),
                **kwargs
            }

            self.routes.append(route_info)
            return endpoint_func

        return decorator

    def get_full_path(self, path: str) -> str:
        """
        Get the full path by combining router prefix with route path.

        Args:
            path: The route path

        Returns:
            Full path with prefix applied
        """
        if not self.prefix:
            return path

        # Handle root path specially
        if path == "/":
            return self.prefix

        # Combine prefix and path, avoiding double slashes
        if path.startswith("/"):
            return self.prefix + path
        else:
            return self.prefix + "/" + path
