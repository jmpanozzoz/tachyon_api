# Function middleware adapters for Tachyon's shared ASGI stack.
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
