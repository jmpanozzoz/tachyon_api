"""Persistent synthetic KYC reference; factory instances own their resources."""
from contextlib import asynccontextmanager
from importlib.metadata import version
import os
import secrets

import anyio
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text, select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import JSONResponse

from tachyon_api import Tachyon, Depends
from tachyon_api.middlewares import CORSMiddleware, SecurityHeadersMiddleware
from tachyon_api.openapi import Info, OpenAPIConfig

from .config import Settings
from .shared.cache import Cache
from .shared.database import database, get_session
from .shared.dependencies import get_current_user, require_admin
from .shared.exceptions import KYCException
from .shared.observability import BUCKETS, Metrics, ObservabilityMiddleware
from .shared.models import Job
from .shared.websocket_manager import issue_ticket, notifications
from .modules.auth.auth_service import hasher
from .modules.auth import router as auth_router
from .modules.customers import router as customers_router
from .modules.verification import router as verification_router

APP_VERSION = "0.2.0"


def create_app(settings=None):
    config = settings or Settings.from_env()
    metrics = Metrics()

    @asynccontextmanager
    async def lifespan(application):
        engine, sessions = database(config.database_url)
        redis = Redis.from_url(config.redis_url, socket_connect_timeout=.25, socket_timeout=.25,
                               max_connections=20, retry_on_timeout=False)
        application.state.engine, application.state.sessions = engine, sessions
        application.state.redis = redis
        application.state.cache = Cache(redis, config.cache_ttl_seconds)
        application.state.hash_limiter = anyio.CapacityLimiter(2)
        try:
            async with engine.connect() as connection:
                if not await connection.scalar(text("SELECT to_regclass('users')")):
                    raise RuntimeError("Reference database is not migrated; run Alembic first")
            application.state.dummy_password_hash = await anyio.to_thread.run_sync(
                hasher.hash, secrets.token_urlsafe(32), limiter=application.state.hash_limiter)
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    application = Tachyon(lifespan=lifespan, max_body_size=1024 * 1024,
        openapi_config=OpenAPIConfig(info=Info(title="Synthetic KYC reference", version=APP_VERSION)))
    application.state.settings = config
    application.state.metrics = metrics
    application.add_middleware(ObservabilityMiddleware, metrics=metrics)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(CORSMiddleware, allow_origins=list(config.allowed_origins),
        allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Correlation-Id"])

    @application.exception_handler(KYCException)
    async def domain_error(request, exc):
        return JSONResponse({"success": False, "error": exc.detail, "code": exc.error_code}, status_code=exc.status_code)

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse({"error": "Database unavailable", "code": "DATABASE_UNAVAILABLE"}, status_code=503)

    application.include_router(auth_router)
    application.include_router(customers_router)
    application.include_router(verification_router)

    @application.get("/")
    async def root():
        return {"status": "healthy", "service": "Synthetic KYC reference", "version": APP_VERSION,
                "framework_version": version("tachyon-api"), "build_revision": os.getenv("SOURCE_REVISION", "unknown")}

    @application.get("/health/live")
    async def live():
        return {"status": "alive"}

    @application.get("/health")
    @application.get("/health/ready")
    async def ready(request: Request):
        try:
            with anyio.fail_after(1):
                async with request.app.state.engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
        except (SQLAlchemyError, TimeoutError):
            return JSONResponse({"status": "not_ready", "database": "down"}, status_code=503)
        try:
            await request.app.state.redis.ping()
            cache = "up"
        except RedisError:
            cache = "degraded"
        return {"status": "ready", "database": "up", "cache": cache,
                "worker": "check durable queue metrics separately"}

    @application.get("/metrics")
    async def metrics_view(request: Request, user: dict = Depends(get_current_user),
                           session: AsyncSession = Depends(get_session)):
        require_admin(user)
        queue = (await session.execute(select(Job.state, func.count()).group_by(Job.state))).all()
        return {"scope": "this_process", "requests": metrics.requests, "inflight": metrics.inflight,
                "transport_errors": metrics.errors, "duration_bucket_bounds_seconds": [*BUCKETS, None],
                "duration_bucket_counts": metrics.buckets, "db_checked_out": request.app.state.engine.pool.checkedout(),
                "durable_queue_states": dict(queue)}

    @application.post("/customers/{customer_id}/notification-ticket")
    async def ticket(customer_id: str, user: dict = Depends(get_current_user),
                     session: AsyncSession = Depends(get_session)):
        return await issue_ticket(session, customer_id, user)

    application.websocket("/ws/notifications/{customer_id}")(notifications)
    return application


app = create_app()
