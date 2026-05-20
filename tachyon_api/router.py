"""Route grouping with shared prefix, tags, and dependencies."""

from functools import partial
from typing import List, Optional, Any, Callable, Dict

from .di import Depends


class Router:
    """Groups routes with a common prefix, tags, and dependencies."""

    def __init__(
        self,
        prefix: str = "",
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[Depends]] = None,
        responses: Optional[Dict[int, Dict[str, Any]]] = None,
    ):
        if prefix and not prefix.startswith("/"):
            prefix = "/" + prefix
        elif prefix is None:
            prefix = ""

        self.prefix = prefix
        self.tags = tags or []
        self.dependencies = dependencies or []
        self.responses = responses or {}
        self.routes: List[Dict[str, Any]] = []

        http_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
        for method in http_methods:
            setattr(
                self,
                method.lower(),
                partial(self._create_route_decorator, http_method=method),
            )

    def _create_route_decorator(self, path: str, *, http_method: str, **kwargs):
        def decorator(endpoint_func: Callable):
            route_tags = list(self.tags)
            if "tags" in kwargs:
                if isinstance(kwargs["tags"], list):
                    route_tags.extend(kwargs["tags"])
                else:
                    route_tags.append(kwargs["tags"])

            if route_tags:
                kwargs["tags"] = route_tags

            route_info = {
                "path": path,
                "method": http_method,
                "func": endpoint_func,
                "dependencies": self.dependencies.copy(),
                **kwargs,
            }

            self.routes.append(route_info)
            return endpoint_func

        return decorator

    def websocket(self, path: str):
        """Decorator to register a WebSocket endpoint with this router."""

        def decorator(endpoint_func: Callable):
            self.routes.append({
                "path": path,
                "method": "WEBSOCKET",
                "func": endpoint_func,
                "is_websocket": True,
            })
            return endpoint_func

        return decorator

    def get_full_path(self, path: str) -> str:
        if not self.prefix:
            return path
        if path == "/":
            return self.prefix
        return self.prefix + (path if path.startswith("/") else "/" + path)
