"""Request-scoped persistence; ownership is enforced by services."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tachyon_api import Depends, injectable
from ...shared.database import get_session
from ...shared.models import Customer


@injectable(scope="request")
class CustomersRepository:
    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session

    async def find_by_id(self, customer_id):
        return await self.session.get(Customer, customer_id)

    async def find_by_user_id(self, user_id):
        return await self.session.scalar(select(Customer).where(Customer.user_id == user_id))

    async def recent(self, limit):
        return (await self.session.scalars(select(Customer).order_by(
            Customer.created_at.desc(), Customer.customer_id).limit(limit))).all()
