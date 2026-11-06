"""A verification and its durable job commit together, before HTTP success."""
from datetime import timedelta
import msgspec
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from tachyon_api import Depends, injectable
from ...shared.dependencies import require_owner
from ...shared.exceptions import KYCException
from ...shared.models import Customer, Verification, Job, now
from .verification_repository import VerificationRepository
from .verification_dto import VerificationResponse


def response(verification):
    values = {field: getattr(verification, field) for field in VerificationResponse.__struct_fields__}
    for field in ("started_at", "completed_at", "expires_at"):
        values[field] = values[field].isoformat() if values[field] else None
    return msgspec.convert(values, type=VerificationResponse)


@injectable(scope="request")
class VerificationService:
    def __init__(self, request: Request, repository: VerificationRepository = Depends()):
        self.repository, self.settings = repository, request.app.state.settings
        self.session = repository.session

    async def start(self, data, user, key):
        if not 1 <= len(key) <= 128 or data.verification_type not in {"standard", "enhanced"}:
            raise KYCException(422, "Invalid verification or idempotency key", "INVALID_VERIFICATION")
        customer = await self.session.get(Customer, data.customer_id)
        require_owner(customer, user)
        existing = await self.repository.by_key(user["user_id"], key)
        if existing:
            return self._existing(existing, data)
        checks = ["identity", "address", "sanctions"]
        if data.verification_type == "enhanced":
            checks += ["pep", "adverse_media"]
        verification = Verification(customer_id=customer.customer_id, owner_id=user["user_id"],
            idempotency_key=key, verification_type=data.verification_type,
            checks=[{"check_type": c, "status": "pending"} for c in checks],
            expires_at=now() + timedelta(seconds=self.settings.verification_timeout_seconds))
        try:
            self.session.add(verification)
            await self.session.flush()
            self.session.add(Job(verification_id=verification.verification_id))
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.repository.by_key(user["user_id"], key)
            if existing is None:
                raise
            return self._existing(existing, data)
        return response(verification)

    def _existing(self, existing, data):
        if existing.customer_id != data.customer_id or existing.verification_type != data.verification_type:
            raise KYCException(409, "Idempotency key used for different input", "IDEMPOTENCY_CONFLICT")
        return response(existing)

    async def get(self, verification_id, user):
        verification = await self.repository.by_id(verification_id)
        if verification is None:
            raise KYCException(404, "Verification not found", "VERIFICATION_NOT_FOUND")
        require_owner(await self.session.get(Customer, verification.customer_id), user)
        return response(verification)
