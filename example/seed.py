"""Explicit synthetic seed. Never runs at application startup."""
import argparse
import asyncio
import getpass
import anyio
from sqlalchemy import select
from .config import Settings
from .shared.database import database
from .shared.models import User
from .modules.auth.auth_service import hasher


async def seed(settings, email, password, admin=False):
    if settings.environment not in {"development", "test"}:
        raise ValueError("Synthetic seeds are restricted to development/test")
    if len(password) < 10 or len(password) > 128:
        raise ValueError("Use a password between 10 and 128 characters")
    engine, sessions = database(settings.database_url)
    try:
        async with sessions() as session, session.begin():
            if await session.scalar(select(User).where(User.email == email)):
                return
            session.add(User(email=email, full_name="Synthetic User", role="admin" if admin else "user",
                             password_hash=await anyio.to_thread.run_sync(hasher.hash, password)))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--admin", action="store_true")
    args = parser.parse_args()
    asyncio.run(seed(Settings.from_env(), args.email.strip().lower(), getpass.getpass("Seed password: "), args.admin))
