"""
Configuration settings for KYC Demo API.

In production, these would come from environment variables.
"""

import os
from dataclasses import dataclass
import secrets


@dataclass
class Settings:
    """Application settings."""
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    # API
    api_title: str = "KYC Demo API"
    api_version: str = "1.0.0"
    
    # Security
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    api_key_header: str = "X-API-Key"
    
    # Mock API Keys (in production, these would be in a database)
    valid_api_keys: tuple = ("demo-api-key-123", "test-api-key-456")
    
    # Verification settings
    verification_timeout_seconds: int = 300  # 5 minutes
    max_document_size_mb: int = 10
    allowed_document_types: tuple = ("image/jpeg", "image/png", "application/pdf")
    
    # Cache
    cache_ttl_seconds: int = 3600  # 1 hour
    
    def __post_init__(self):
        development = self.environment.lower() in {"development", "test"}
        insecure = self.secret_key in {
            "super-secret-key-change-in-production", "change-me", "secret",
        }
        if not development and (len(self.secret_key) < 32 or insecure):
            raise ValueError("SECRET_KEY must be a non-demo key of at least 32 characters outside development/test")
        if not self.secret_key:
            self.secret_key = secrets.token_urlsafe(32)

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        environment = os.getenv("ENVIRONMENT", "development")
        return cls(
            environment=environment,
            debug=os.getenv("DEBUG", "true" if environment.lower() in {"development", "test"} else "false").lower() == "true",
            secret_key=os.getenv("SECRET_KEY", ""),
        )


# Global settings instance
settings = Settings.from_env()
