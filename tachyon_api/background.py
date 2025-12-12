"""
Tachyon Background Tasks Module

Provides background task functionality for running tasks after response is sent.
"""

import asyncio
from typing import Any, Callable, List, Tuple


class BackgroundTasks:
    """
    Background tasks that run after the response has been sent.

    Tasks are executed in order after the response is complete.
    Errors in tasks are caught and logged but don't affect the response.

    Example:
        @app.get("/send-notification")
        def send_notification(background_tasks: BackgroundTasks):
            background_tasks.add_task(send_email, "user@example.com", "Hello!")
            return {"message": "Notification scheduled"}
    """

    def __init__(self):
        self._tasks: List[Tuple[Callable, tuple, dict]] = []

    def add_task(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Add a task to be run in the background.

        Args:
            func: The function to call. Can be sync or async.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Example:
            background_tasks.add_task(write_log, "User logged in")
            background_tasks.add_task(send_email, to="user@example.com", subject="Hi")
        """
        self._tasks.append((func, args, kwargs))

    async def run_tasks(self) -> None:
        """
        Execute all queued background tasks.

        This method is called automatically after the response is sent.
        Each task is run in order, and errors are caught to prevent
        one failing task from stopping the others.
        """
        for func, args, kwargs in self._tasks:
            try:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                # Log error but continue with other tasks
                # In production, you'd want proper logging here
                pass

    def __len__(self) -> int:
        """Return the number of pending tasks."""
        return len(self._tasks)

    def __bool__(self) -> bool:
        """BackgroundTasks is always truthy (to allow `if background_tasks:`)."""
        return True
