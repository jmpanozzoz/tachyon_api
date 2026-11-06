"""Run with python -m example.worker; no HTTP request resources are captured."""
import asyncio
import logging
import signal

from redis.asyncio import Redis

from .config import Settings
from .shared.cache import Cache
from .shared.database import database
from .modules.verification.jobs import claim, process, publish_one, prune

logger = logging.getLogger("reference.worker")


async def run(settings=None):
    settings = settings or Settings.from_env()
    engine, sessions = database(settings.database_url)
    redis = Redis.from_url(settings.redis_url, socket_connect_timeout=.25, socket_timeout=.25,
                           max_connections=10, retry_on_timeout=False)
    cache = Cache(redis, settings.cache_ttl_seconds)
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    signals = (signal.SIGTERM, signal.SIGINT)
    for signum in signals:
        loop.add_signal_handler(signum, stopped.set)
    try:
        iteration = 0
        while not stopped.is_set():
            claimed = None
            try:
                claimed = await claim(sessions, settings)
                if claimed:
                    await process(sessions, settings, claimed)
                for _ in range(20):
                    if not await publish_one(sessions, cache):
                        break
                if iteration % 60 == 0:
                    await prune(sessions)
                iteration += 1
            except Exception as exc:
                # No SQL parameters, credentials or customer payloads in logs.
                logger.error("Worker operation failed (%s)", type(exc).__name__)
            try:
                await asyncio.wait_for(stopped.wait(), timeout=.01 if claimed else .5)
            except asyncio.TimeoutError:
                pass
    finally:
        for signum in signals:
            loop.remove_signal_handler(signum)
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
