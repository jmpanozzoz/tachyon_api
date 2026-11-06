"""Verification persistence using the same request-owned session."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tachyon_api import Depends, injectable
from ...shared.database import get_session
from ...shared.models import Verification


@injectable(scope="request")
class VerificationRepository:
    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session

    async def by_id(self, verification_id):
        return await self.session.get(Verification, verification_id)

    async def by_key(self, owner_id, key):
        return await self.session.scalar(select(Verification).where(
            Verification.owner_id == owner_id, Verification.idempotency_key == key))
