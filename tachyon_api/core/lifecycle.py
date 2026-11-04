"""Startup/shutdown handlers and user lifespan state."""
import logging
from contextlib import asynccontextmanager

from starlette._utils import is_async_callable
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)


class LifecycleManager:
    def __init__(self, user_lifespan=None):
        self._user_lifespan = user_lifespan
        self._startup_handlers = []
        self._shutdown_handlers = []

    def create_combined_lifespan(self):
        @asynccontextmanager
        async def combined_lifespan(app):
            for handler in self._startup_handlers:
                try:
                    if is_async_callable(handler):
                        await handler()
                    else:
                        await run_in_threadpool(handler)
                except Exception as exc:
                    raise RuntimeError(f"Startup handler {getattr(handler, '__name__', repr(handler))!r} raised: {exc}") from exc
            try:
                if self._user_lifespan is not None:
                    async with self._user_lifespan(app) as state:
                        yield state
                else:
                    yield
            finally:
                for handler in self._shutdown_handlers:
                    try:
                        if is_async_callable(handler):
                            await handler()
                        else:
                            await run_in_threadpool(handler)
                    except Exception:
                        logger.exception("Shutdown handler %r failed", handler)
        return combined_lifespan

    def on_event_decorator(self, event_type):
        def decorator(func):
            if event_type == "startup":
                self._startup_handlers.append(func)
            elif event_type == "shutdown":
                self._shutdown_handlers.append(func)
            else:
                raise ValueError(f"Invalid event type: {event_type}. Use 'startup' or 'shutdown'.")
            return func
        return decorator
