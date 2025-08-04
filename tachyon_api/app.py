import asyncio
import inspect
from functools import partial
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


class Tachyon:
    def __init__(self):
        self._router = Starlette()
        self.routes = []

        http_methods = [
            "GET", "POST", "PUT", "DELETE",
            "PATCH", "OPTIONS", "HEAD"
        ]

        for method in http_methods:
            setattr(self, method.lower(), partial(self._create_decorator, http_method=method))

    def _create_decorator(self, path: str, *, http_method: str):
        """
        This method creates a decorator for the specified HTTP method.
        """
        def decorator(endpoint_func):
            self._add_route(path, endpoint_func, http_method)
            return endpoint_func

        return decorator

    def _add_route(self, path: str, endpoint_func, method: str):
        """
        This method adds a route to the Tachyon application.
        It wraps the endpoint function in an async handler that returns a JSONResponse.
        The endpoint function can be a coroutine or a regular function.
        The method parameter specifies the HTTP method for the route (e.g., GET, POST).
        """

        async def handler(request):
            # In next phases, this is where parameter injection logic will go
            # such as Body(), Query(), etc.
            if asyncio.iscoroutinefunction(endpoint_func):
                payload = await endpoint_func()
            else:
                payload = endpoint_func()
            return JSONResponse(payload)

        route = Route(path, endpoint=handler, methods=[method])
        self._router.routes.append(route)
        self.routes.append({"path": path, "method": method, "func": endpoint_func})


    async def __call__(self, scope, receive, send):
        await self._router(scope, receive, send)
