# Route registry — single source of truth for what's registered.
# Cold path: only written at startup; read for introspection (CLI, OpenAPI).

from typing import Any, Callable, Dict, List


class RouteRegistry:
    """Storage of registered routes. Answers: "what routes are registered?" """

    __slots__ = ("_routes",)

    def __init__(self) -> None:
        self._routes: List[Dict[str, Any]] = []

    def add(self, path: str, method: str, func: Callable, **kwargs: Any) -> None:
        self._routes.append({"path": path, "method": method, "func": func, **kwargs})

    @property
    def routes(self) -> List[Dict[str, Any]]:
        return self._routes
