from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport


@asynccontextmanager
async def create_client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
