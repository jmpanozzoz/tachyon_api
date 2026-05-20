# Internal helpers for integrating middlewares into Starlette's stack
from starlette.middleware import Middleware


def apply_middleware_to_router(router_app, middleware_class, **options):
    router_app.user_middleware.insert(0, Middleware(middleware_class, **options))
    router_app.middleware_stack = router_app.build_middleware_stack()


def create_decorated_middleware_class(middleware_func, middleware_type: str = "http"):
    """Wraps a function(scope, receive, send, app) as an ASGI middleware class."""

    class DecoratedMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope.get("type") == middleware_type or middleware_type == "*":
                return await middleware_func(scope, receive, send, self.app)
            return await self.app(scope, receive, send)

    return DecoratedMiddleware
