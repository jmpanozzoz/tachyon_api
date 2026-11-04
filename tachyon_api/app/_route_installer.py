# Cold path — orchestrates the installation of a single route across the
# subsystems that need to know about it: handler factory, trie, registry, openapi.

from typing import Any, Callable
import inspect

from ..processing.compiler import compile_endpoint
from ..di import Depends
from ..processing.dependencies._sig_cache import prepare_dependency, get_signature
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
        supported = {"response_model", "dependencies", "include_in_schema", "summary", "description", "tags", "responses"}
        unknown = kwargs.keys() - supported
        if unknown:
            raise TypeError(f"Unsupported route options: {', '.join(sorted(unknown))}")
        dependencies = []
        for marker in kwargs.get("dependencies", ()):
            if not isinstance(marker, Depends) or marker.dependency is None:
                raise TypeError("Route dependencies must be Depends(callable)")
            prepare_dependency(marker.dependency)
            dependencies.append(marker.dependency)
        response_model = kwargs.get("response_model")
        compiled = compile_endpoint(endpoint_func, path)
        bound_names = {param.name for param in compiled.params}
        for param in get_signature(endpoint_func).parameters.values():
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                raise TypeError("Endpoint signatures cannot contain *args or **kwargs")
            if param.default is inspect.Parameter.empty and param.name not in bound_names:
                raise TypeError(f"Cannot bind required endpoint parameter '{param.name}'; use a parameter marker or dependency")

        if not compiled.has_params and not compiled.has_callable_deps and not dependencies:
            handler = _ASGIHandler(
                self._app._fast_asgi_factory.build(compiled, response_model)
            )
        else:
            handler = self._app._handler_factory.build(compiled, response_model, tuple(dependencies))

        if kwargs.get("include_in_schema", True):
            self._app.openapi_generator.generate_route(
                path, method, endpoint_func, **kwargs
            )

        self._app._trie.add(path, method, handler)
        self._app._registry.add(path, method, endpoint_func, **kwargs)
