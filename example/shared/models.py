"""PostgreSQL persistence; msgspec DTOs stay at the HTTP boundary."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


def identifier():
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), default="user")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')"),)


class Customer(Base):
    __tablename__ = "customers"
    customer_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), unique=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(50))
    date_of_birth: Mapped[str | None] = mapped_column(String(10))
    address: Mapped[dict | None] = mapped_column(JSONB)
    kyc_status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Verification(Base):
    __tablename__ = "verifications"
    verification_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    verification_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    checks: Mapped[list] = mapped_column(JSONB, default=list)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_verification_idempotency"),
        CheckConstraint("verification_type IN ('standard', 'enhanced')"),
    )


class Job(Base):
    __tablename__ = "verification_jobs"
    verification_id: Mapped[str] = mapped_column(ForeignKey("verifications.verification_id"), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(32))
    __table_args__ = (CheckConstraint("state IN ('pending', 'running', 'done', 'failed')"),)


class Event(Base):
    __tablename__ = "notification_events"
    event_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"))
    payload: Mapped[dict] = mapped_column(JSONB)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WebSocketTicket(Base):
    __tablename__ = "websocket_tickets"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
