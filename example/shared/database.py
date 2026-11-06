"""Application engine, one session per request or independent worker task."""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request


def database(url):
    engine = create_async_engine(url, pool_size=5, max_overflow=5, pool_timeout=3,
                                 connect_args={"timeout": 3, "command_timeout": 5})
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request):
    async with request.app.state.sessions() as session:
        # Services commit before returning success. Exit rolls back pending work.
        yield session
