"""Per-request tasks around an existing response, without changing its state."""
from starlette.responses import Response


class _BackgroundResponse(Response):
    def __init__(self, response, tasks):
        self._response = response
        self._tasks = tasks

    def __getattr__(self, name):
        return getattr(self._response, name)

    async def __call__(self, scope, receive, send):
        await self._response(scope, receive, send)
        await self._tasks.run_tasks()
