"""Customer operations authorize before returning a result or cache value."""
import msgspec
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from tachyon_api import Depends, injectable
from ...shared.dependencies import require_owner, require_admin
from ...shared.exceptions import KYCException
from ...shared.models import Customer
from .customers_repository import CustomersRepository
from .customers_dto import CustomerResponse


def response(customer):
    values = {field: getattr(customer, field) for field in CustomerResponse.__struct_fields__}
    for field in ("created_at", "updated_at"):
        values[field] = values[field].isoformat()
    return msgspec.convert(values, type=CustomerResponse)


@injectable(scope="request")
class CustomersService:
    def __init__(self, request: Request, repository: CustomersRepository = Depends()):
        self.repository, self.cache = repository, request.app.state.cache

    async def create_customer(self, user_id, data):
        existing = await self.repository.find_by_user_id(user_id)
        if existing:
            return response(existing)
        values = msgspec.to_builtins(data)
        if any(not 1 <= len(values[key]) <= 120 for key in ("first_name", "last_name")) or len(data.email) > 254:
            raise KYCException(422, "Invalid customer fields", "INVALID_CUSTOMER")
        customer = Customer(user_id=user_id, **values)
        self.repository.session.add(customer)
        try:
            await self.repository.session.commit()
        except IntegrityError:
            await self.repository.session.rollback()
            raise KYCException(409, "Customer already exists", "CUSTOMER_CONFLICT") from None
        return response(customer)

    async def get_customer(self, customer_id, user):
        # DB ownership is checked on every read, even with a cache hit.
        customer = await self.repository.find_by_id(customer_id)
        require_owner(customer, user)
        key = f"reference:customer:{'admin' if user['role'] == 'admin' else user['user_id']}:{customer_id}"
        cached = await self.cache.get(key)
        if cached:
            try:
                return msgspec.convert(cached, type=CustomerResponse)
            except (msgspec.ValidationError, TypeError):
                pass
        value = response(customer)
        await self.cache.set(key, msgspec.to_builtins(value))
        return value

    async def mine(self, user):
        customer = await self.repository.find_by_user_id(user["user_id"])
        require_owner(customer, user)
        return response(customer)

    async def recent(self, user, limit):
        require_admin(user)
        if not 1 <= limit <= 100:
            raise KYCException(422, "limit must be between 1 and 100", "INVALID_LIMIT")
        return [response(c) for c in await self.repository.recent(limit)]
