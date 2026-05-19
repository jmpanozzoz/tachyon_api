"""Tasks queued to run after the response is sent."""

import asyncio
from typing import Any, Callable, List, Tuple


class BackgroundTasks:
    """Collects sync/async tasks to execute after the response is sent."""

    def __init__(self):
        self._tasks: List[Tuple[Callable, tuple, dict]] = []

    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self._tasks.append((func, args, kwargs))

    async def run_tasks(self) -> None:
        for func, args, kwargs in self._tasks:
            try:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    def __len__(self) -> int:
        return len(self._tasks)

    def __bool__(self) -> bool:
        return True
