# Internal core helpers for Tachyon middleware integration
from starlette.middleware import Middleware


def apply_middleware_to_router(router_app, middleware_class, **options):
    """
    Insert an ASGI middleware into Starlette's stack and rebuild the stack.

    Args:
        router_app: internal Starlette instance (app._router)
        middleware_class: ASGI middleware class
        **options: kwargs passed to the middleware constructor
    """
    router_app.user_middleware.insert(0, Middleware(middleware_class, **options))
    router_app.middleware_stack = router_app.build_middleware_stack()


def create_decorated_middleware_class(middleware_func, middleware_type: str = "http"):
    """
    Create an ASGI middleware class from a decorated function with the signature
    (scope, receive, send, app).

    Args:
        middleware_func: middleware function provided to the decorator
        middleware_type: type ("http" by default) or "*" for all

    Returns:
        Middleware class that invokes the decorated function
    """

    class DecoratedMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope.get("type") == middleware_type or middleware_type == "*":
                return await middleware_func(scope, receive, send, self.app)
            return await self.app(scope, receive, send)

    return DecoratedMiddleware
