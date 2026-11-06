"""Adapt generator providers to one request-owned async exit stack."""
from contextlib import asynccontextmanager, contextmanager

from anyio import CapacityLimiter, to_thread


@asynccontextmanager
async def resource_context(provider, args, kwargs, kind):
    if kind == "async":
        async with asynccontextmanager(provider)(*args, **kwargs) as value:
            yield value
        return
    manager = contextmanager(provider)(*args, **kwargs)
    # Exit cannot wait for the same saturated limiter as resource acquisition.
    exit_limiter = CapacityLimiter(1)
    value = await to_thread.run_sync(manager.__enter__)
    try:
        yield value
    except BaseException as exc:
        suppressed = await to_thread.run_sync(
            manager.__exit__, type(exc), exc, exc.__traceback__,
            limiter=exit_limiter, abandon_on_cancel=True,
        )
        if not suppressed:
            raise
    else:
        await to_thread.run_sync(
            manager.__exit__, None, None, None,
            limiter=exit_limiter, abandon_on_cancel=True,
        )
