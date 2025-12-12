"""
Configuration settings for KYC Demo API.

In production, these would come from environment variables.
"""

import os
from dataclasses import dataclass


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
    secret_key: str = "super-secret-key-change-in-production"
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
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=os.getenv("DEBUG", "true").lower() == "true",
            secret_key=os.getenv("SECRET_KEY", cls.secret_key),
        )


# Global settings instance
settings = Settings.from_env()
