"""Argon2id runs off the event loop; successful responses follow commit."""
from datetime import timedelta
import hashlib
import hmac

import anyio
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
import jwt
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from tachyon_api import Depends, injectable
from ...shared.exceptions import KYCException, UnauthorizedError
from ...shared.models import User, LoginAttempt, now
from .auth_repository import AuthRepository
from .auth_dto import UserResponse, TokenResponse

# Bounded work is shared by all hash/verify calls in this application.
hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def response(user):
    return UserResponse(user_id=user.user_id, email=user.email, full_name=user.full_name,
                        role=user.role, is_verified=user.is_verified)


@injectable(scope="request")
class AuthService:
    def __init__(self, request: Request, repository: AuthRepository = Depends()):
        self.request, self.repository = request, repository
        self.session = repository.session
        self.settings = request.app.state.settings

    async def register(self, data):
        email = data.email.strip().lower()
        if not (3 <= len(email) <= 254 and "@" in email and 10 <= len(data.password) <= 128
                and 1 <= len(data.full_name.strip()) <= 120):
            raise KYCException(422, "Invalid registration fields", "INVALID_REGISTRATION")
        password_hash = await anyio.to_thread.run_sync(
            hasher.hash, data.password, limiter=self.request.app.state.hash_limiter)
        user = User(email=email, full_name=data.full_name.strip(), password_hash=password_hash)
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise KYCException(409, "Registration unavailable", "REGISTRATION_CONFLICT") from None
        return response(user)

    async def login(self, data):
        email = data.email.strip().lower()
        # One account key and one client key prevent easy account/IP bypasses.
        # A trusted proxy must sanitize the actual client address before ASGI.
        client = self.request.client.host if self.request.client else "unknown"
        for kind, value, maximum in (("account", email, self.settings.login_limit),
                                      ("client", client, self.settings.login_limit * 10)):
            digest = hmac.new(self.settings.secret_key.encode(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()
            stmt = insert(LoginAttempt).values(digest=digest, count=1, expires_at=now() + timedelta(minutes=1))
            stmt = stmt.on_conflict_do_update(index_elements=[LoginAttempt.digest],
                set_={"count": LoginAttempt.count + 1})
            await self.session.execute(delete(LoginAttempt).where(LoginAttempt.expires_at < now()))
            await self.session.execute(stmt)
            attempt = await self.session.scalar(select(LoginAttempt).where(LoginAttempt.digest == digest))
            if attempt.count > maximum:
                await self.session.commit()
                raise KYCException(429, "Try again later", "RATE_LIMITED")
        await self.session.commit()
        user = await self.repository.by_email(email)
        encoded = user.password_hash if user else self.request.app.state.dummy_password_hash
        def verify():
            try:
                return hasher.verify(encoded, data.password)
            except VerificationError:
                return False
        valid = await anyio.to_thread.run_sync(verify, limiter=self.request.app.state.hash_limiter)
        if not valid or user is None or not user.active:
            raise UnauthorizedError("Invalid email or password")
        timestamp = now()
        token = jwt.encode({"sub": user.user_id, "iat": timestamp,
                            "exp": timestamp + timedelta(hours=self.settings.jwt_expiration_hours),
                            "iss": self.settings.jwt_issuer, "aud": self.settings.jwt_audience},
                           self.settings.secret_key, algorithm=self.settings.jwt_algorithm)
        return TokenResponse(access_token=token, expires_in=self.settings.jwt_expiration_hours * 3600)
