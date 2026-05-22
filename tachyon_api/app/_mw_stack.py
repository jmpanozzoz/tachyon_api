# Cold path — invoked at startup and when add_middleware is called.
# Stores user middlewares and builds the wrapped ASGI app.

from typing import Any, Callable, Dict, List


class MiddlewareStack:
    """Stores user middlewares and builds the wrapped HTTP ASGI app."""

    __slots__ = ("_middlewares",)

    def __init__(self) -> None:
        self._middlewares: List[Dict[str, Any]] = []

    def add(self, middleware_class: Any, **options: Any) -> None:
        self._middlewares.append({"func": middleware_class, "options": options})

    def build(self, inner_app: Callable) -> Callable:
        """Wrap inner_app with all registered middlewares (outermost first)."""
        app = inner_app
        for mw in reversed(self._middlewares):
            app = mw["func"](app=app, **mw["options"])
        return app

    @property
    def middlewares(self) -> List[Dict[str, Any]]:
        return self._middlewares
