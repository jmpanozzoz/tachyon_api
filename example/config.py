"""Explicit configuration; importing the app never connects to services."""
from dataclasses import dataclass
import os
import secrets


@dataclass
class Settings:
    environment: str = "development"
    debug: bool = True
    secret_key: str = ""
    database_url: str = "postgresql+asyncpg://tachyon:local-only@127.0.0.1:5432/tachyon"
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "tachyon-reference"
    jwt_audience: str = "tachyon-reference-api"
    jwt_expiration_hours: int = 1
    cache_ttl_seconds: int = 30
    verification_timeout_seconds: int = 300
    provider_result: str = "passed"
    job_lease_seconds: int = 30
    job_max_attempts: int = 5
    login_limit: int = 10
    websocket_recheck_seconds: float = 10
    websocket_session_seconds: float = 300
    allowed_origins: tuple = ("http://localhost:3000", "http://localhost:5173")

    def __post_init__(self):
        development = self.environment.lower() in {"development", "test"}
        if self.secret_key and len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        if self.jwt_algorithm != "HS256":
            raise ValueError("The reference supports HS256 tokens only")
        if not development and (len(self.secret_key) < 32 or self.secret_key in {
            "super-secret-key-change-in-production", "change-me", "secret",
        }):
            raise ValueError("SECRET_KEY must be a non-demo key of at least 32 characters outside development/test")
        if not development and (self.debug or "local-only" in self.database_url):
            raise ValueError("Production requires DEBUG=false and an explicit DATABASE_URL")
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg://")
        if self.provider_result not in {"passed", "failed", "timeout"}:
            raise ValueError("PROVIDER_RESULT must be passed, failed or timeout")
        if min(self.job_lease_seconds, self.job_max_attempts, self.login_limit) < 1 or min(self.websocket_recheck_seconds, self.websocket_session_seconds) <= 0:
            raise ValueError("Job and login limits must be positive")
        if not self.secret_key:
            self.secret_key = secrets.token_urlsafe(32)

    @classmethod
    def from_env(cls):
        environment = os.getenv("ENVIRONMENT", "development")
        return cls(
            environment=environment,
            debug=os.getenv("DEBUG", "true" if environment.lower() in {"development", "test"} else "false").lower() == "true",
            secret_key=os.getenv("SECRET_KEY", ""),
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            provider_result=os.getenv("PROVIDER_RESULT", "passed"),
            allowed_origins=tuple(x.strip() for x in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if x.strip()),
        )
