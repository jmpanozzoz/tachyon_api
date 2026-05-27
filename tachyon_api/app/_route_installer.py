# Cold path — orchestrates the installation of a single route across the
# subsystems that need to know about it: handler factory, trie, registry, openapi.

from typing import Any, Callable

from ..processing.compiler import compile_endpoint
from ._asgi_handler import _ASGIHandler


class RouteInstaller:
    """Installs one route across trie, registry, and OpenAPI generator."""

    __slots__ = ("_app",)

    def __init__(self, app) -> None:
        self._app = app

    def install(
        self,
        path: str,
        method: str,
        endpoint_func: Callable,
        **kwargs: Any,
    ) -> None:
        response_model = kwargs.get("response_model")
        compiled = compile_endpoint(endpoint_func, path)

        if not compiled.has_params and not compiled.has_callable_deps:
            handler = _ASGIHandler(
                self._app._fast_asgi_factory.build(compiled, response_model)
            )
        else:
            handler = self._app._handler_factory.build(compiled, response_model)

        self._app._trie.add(path, method, handler)
        self._app._registry.add(path, method, endpoint_func, **kwargs)

        if kwargs.get("include_in_schema", True):
            self._app.openapi_generator.generate_route(
                path, method, endpoint_func, **kwargs
            )
