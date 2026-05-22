"""Startup/shutdown lifecycle management."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class LifecycleManager:
    def __init__(self, user_lifespan: Optional[Callable] = None):
        self._user_lifespan = user_lifespan
        self._startup_handlers: List[Callable] = []
        self._shutdown_handlers: List[Callable] = []

    def create_combined_lifespan(self):
        # Captures self by reference so handlers registered after this call are still run
        lifecycle_manager = self

        @asynccontextmanager
        async def combined_lifespan(app):
            for handler in lifecycle_manager._startup_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                except Exception as exc:
                    raise RuntimeError(
                        f"Startup handler {handler.__name__!r} raised: {exc}"
                    ) from exc

            if lifecycle_manager._user_lifespan is not None:
                async with lifecycle_manager._user_lifespan(app):
                    yield
            else:
                yield

            for handler in lifecycle_manager._shutdown_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                except Exception as exc:
                    logger.warning("Shutdown handler %r failed: %s", handler.__name__, exc, exc_info=True)

        return combined_lifespan

    def on_event_decorator(self, event_type: str):
        def decorator(func: Callable):
            if event_type == "startup":
                self._startup_handlers.append(func)
            elif event_type == "shutdown":
                self._shutdown_handlers.append(func)
            else:
                raise ValueError(
                    f"Invalid event type: {event_type}. Use 'startup' or 'shutdown'."
                )
            return func

        return decorator

