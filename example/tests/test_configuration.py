"""Environment security policy is explicit and deterministic under test."""

import pytest

from example.config import Settings


@pytest.mark.parametrize("environment", ["production", "staging"])
@pytest.mark.parametrize("secret", ["", "short", "super-secret-key-change-in-production"])
def test_non_development_requires_non_demo_secret(monkeypatch, environment, secret):
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("SECRET_KEY", secret)
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings.from_env()


def test_production_uses_explicit_secret_and_debug_defaults_off(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a-deliberate-production-secret-key-for-tests")
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://explicit@localhost/example")
    settings = Settings.from_env()
    assert settings.secret_key == "a-deliberate-production-secret-key-for-tests"
    assert settings.debug is False


def test_development_generates_ephemeral_key(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr("example.config.secrets.token_urlsafe", lambda length: "test-generated-key")
    assert Settings.from_env().secret_key == "test-generated-key"
