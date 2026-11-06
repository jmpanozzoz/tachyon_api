"""Current database identity/role, never authorization from JWT claims alone."""
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tachyon_api import Depends
from tachyon_api.security import HTTPBearer, HTTPAuthorizationCredentials

from .database import get_session
from .exceptions import UnauthorizedError, KYCException
from .models import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if credentials is None:
        raise UnauthorizedError("Missing authentication token")
    settings = request.app.state.settings
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key,
                             algorithms=[settings.jwt_algorithm],
                             issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                             options={"require": ["sub", "exp", "iat", "iss", "aud"]})
        user = await session.get(User, payload["sub"])
        if user is None or not user.active:
            raise UnauthorizedError()
        return {"user_id": user.user_id, "email": user.email, "role": user.role,
                "full_name": user.full_name, "is_verified": user.is_verified}
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid or expired token") from None


def require_owner(customer, user):
    if customer is None or (customer.user_id != user["user_id"] and user["role"] != "admin"):
        raise KYCException(404, "Customer not found", "CUSTOMER_NOT_FOUND")


def require_admin(user):
    if user["role"] != "admin":
        raise KYCException(403, "Administrator role required", "FORBIDDEN")
