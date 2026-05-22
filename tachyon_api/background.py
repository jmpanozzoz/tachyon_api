"""Tasks queued to run after the response is sent."""

import asyncio
import logging
from typing import Any, Callable, List, Tuple

logger = logging.getLogger(__name__)


class BackgroundTasks:
    """Collects sync/async tasks to execute after the response is sent."""

    __slots__ = ("_tasks",)

    def __init__(self):
        self._tasks: List[Tuple[Callable, bool, tuple, dict]] = []

    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        # Cache async flag at add_task time to avoid checking the result after calling
        self._tasks.append((func, asyncio.iscoroutinefunction(func), args, kwargs))

    async def run_tasks(self) -> None:
        for func, is_async, args, kwargs in self._tasks:
            try:
                if is_async:
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
            except Exception as exc:
                logger.warning("Background task %s failed: %s", func.__name__, exc, exc_info=True)

    def __len__(self) -> int:
        return len(self._tasks)

    def __bool__(self) -> bool:
        return bool(self._tasks)
