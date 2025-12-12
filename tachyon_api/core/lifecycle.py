"""
Lifecycle event management for Tachyon applications.

Handles:
- User-provided lifespan context managers
- @app.on_event('startup') handlers
- @app.on_event('shutdown') handlers
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Callable, List, Optional


class LifecycleManager:
    """
    Manages application lifecycle events (startup/shutdown).
    
    This class encapsulates the logic for:
    - Registering startup/shutdown handlers via decorators
    - Combining user-provided lifespan with event handlers
    - Executing handlers in the correct order
    """
    
    def __init__(self, user_lifespan: Optional[Callable] = None):
        """
        Initialize lifecycle manager.
        
        Args:
            user_lifespan: Optional async context manager for startup/shutdown
        """
        self._user_lifespan = user_lifespan
        self._startup_handlers: List[Callable] = []
        self._shutdown_handlers: List[Callable] = []
    
    def create_combined_lifespan(self):
        """
        Create a combined lifespan context manager that handles both
        user-provided lifespan and on_event handlers.

        Note: This returns a factory that captures `self` and dynamically
        accesses handlers at runtime (not at definition time).
        
        Returns:
            An async context manager function compatible with Starlette
        """
        lifecycle_manager = self

        @asynccontextmanager
        async def combined_lifespan(app):
            # Run startup handlers (accessed dynamically)
            for handler in lifecycle_manager._startup_handlers:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()

            # Run user-provided lifespan if any
            if lifecycle_manager._user_lifespan is not None:
                # Pass the app to user lifespan (it expects the Tachyon app)
                async with lifecycle_manager._user_lifespan(app):
                    yield
            else:
                yield

            # Run shutdown handlers (accessed dynamically)
            for handler in lifecycle_manager._shutdown_handlers:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()

        return combined_lifespan
    
    def on_event_decorator(self, event_type: str):
        """
        Create a decorator to register startup or shutdown event handlers.

        Args:
            event_type: Either 'startup' or 'shutdown'

        Returns:
            A decorator that registers the handler function

        Example:
            @app.on_event('startup')
            async def on_startup():
                print('Starting up...')

            @app.on_event('shutdown')
            def on_shutdown():
                print('Shutting down...')
        """

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

