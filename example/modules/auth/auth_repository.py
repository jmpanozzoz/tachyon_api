"""Authentication storage shares the request session, never a singleton."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tachyon_api import Depends, injectable
from ...shared.database import get_session
from ...shared.models import User


@injectable(scope="request")
class AuthRepository:
    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session

    async def by_email(self, email):
        return await self.session.scalar(select(User).where(User.email == email))
