"""Adapt generator providers to one request-owned async exit stack."""
from contextlib import asynccontextmanager, contextmanager
import logging
from threading import Event, Lock

from anyio import CapacityLimiter, move_on_after, sleep, to_thread


@asynccontextmanager
async def resource_context(provider, args, kwargs, kind):
    if kind == "async":
        async with asynccontextmanager(provider)(*args, **kwargs) as value:
            yield value
        return
    manager = contextmanager(provider)(*args, **kwargs)
    # Exit cannot wait for the same saturated limiter as resource acquisition.
    exit_limiter = CapacityLimiter(1)
    lock, done = Lock(), Event()
    state = {"entered": False, "closed": False, "abandoned": None}

    def close_once(exc_info):
        with lock:
            if state["closed"]:
                return False
            state["closed"] = True
        return manager.__exit__(*exc_info)

    def enter():
        try:
            value = manager.__enter__()
            with lock:
                state["entered"] = True
                abandoned = state["abandoned"]
            if abandoned is not None:
                try:
                    close_once(abandoned)
                except BaseException as exc:
                    logging.getLogger("tachyon.dependencies").error("Abandoned dependency cleanup failed (%s)", type(exc).__name__)
            return value
        finally:
            done.set()

    try:
        value = await to_thread.run_sync(enter)
    except BaseException as exc:
        # A raw asyncio Task.cancel() can interrupt the await while its worker
        # still enters. Explicitly transfer ownership; never rely on generator GC.
        from ..scope import DEPENDENCY_CLEANUP_TIMEOUT
        error = (type(exc), exc, exc.__traceback__)
        with lock:
            state["abandoned"] = error
            entered = state["entered"]
        with move_on_after(DEPENDENCY_CLEANUP_TIMEOUT, shield=True):
            if entered:
                try:
                    await to_thread.run_sync(close_once, error, limiter=exit_limiter, abandon_on_cancel=True)
                except BaseException as cleanup_error:
                    logging.getLogger("tachyon.dependencies").error("Dependency acquisition cleanup failed (%s)", type(cleanup_error).__name__)
            while not done.is_set():
                await sleep(.001)
        raise
    try:
        yield value
    except BaseException as exc:
        suppressed = await to_thread.run_sync(
            close_once, (type(exc), exc, exc.__traceback__),
            limiter=exit_limiter, abandon_on_cancel=True,
        )
        if not suppressed:
            raise
    else:
        await to_thread.run_sync(
            close_once, (None, None, None),
            limiter=exit_limiter, abandon_on_cancel=True,
        )
