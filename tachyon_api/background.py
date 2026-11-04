"""Tasks executed after response transmission, before request cleanup."""

import inspect
import logging

from starlette.concurrency import run_in_threadpool
from starlette._utils import is_async_callable

logger = logging.getLogger(__name__)


class BackgroundTasks:
    __slots__ = ("_tasks",)

    def __init__(self):
        self._tasks = []

    def add_task(self, func, *args, **kwargs):
        self._tasks.append((func, is_async_callable(func), args, kwargs))

    async def run_tasks(self):
        for func, is_async, args, kwargs in self._tasks:
            try:
                result = await func(*args, **kwargs) if is_async else await run_in_threadpool(func, *args, **kwargs)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Background task %r failed", func)

    def __len__(self):
        return len(self._tasks)

    def __bool__(self):
        return bool(self._tasks)
