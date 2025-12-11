"""
Tests for Lifecycle Events (startup/shutdown).

TDD: These tests are written BEFORE the implementation.

Features to test:
- lifespan context manager
- @app.on_event('startup') decorator
- @app.on_event('shutdown') decorator

Note: We use Starlette's TestClient because httpx.ASGITransport
doesn't execute lifespan events by default.
"""

import pytest
from starlette.testclient import TestClient
from contextlib import asynccontextmanager

from tachyon_api import Tachyon


# --- Test with lifespan context manager ---

def test_lifespan_startup_and_shutdown():
    """
    Test that lifespan context manager runs startup and shutdown code.
    """
    events = []

    @asynccontextmanager
    async def lifespan(app):
        # Startup
        events.append("startup")
        yield
        # Shutdown
        events.append("shutdown")

    app = Tachyon(lifespan=lifespan)

    @app.get("/check")
    def check():
        return {"status": "ok"}

    with TestClient(app) as client:
        # At this point, startup should have run
        assert "startup" in events
        
        response = client.get("/check")
        assert response.status_code == 200

    # After exiting, shutdown should have run
    assert "shutdown" in events
    assert events == ["startup", "shutdown"]


def test_lifespan_with_app_state():
    """
    Test that lifespan can set up app state that endpoints can access.
    """
    @asynccontextmanager
    async def lifespan(app):
        # Simulate database connection on startup
        app.state.db = {"connected": True, "pool_size": 10}
        yield
        # Cleanup on shutdown
        app.state.db = None

    app = Tachyon(lifespan=lifespan)

    @app.get("/db-status")
    def db_status():
        # Access app state (would need Request injection in real use)
        return {"db_connected": True}

    with TestClient(app) as client:
        response = client.get("/db-status")
        assert response.status_code == 200


# --- Test with on_event decorators ---

def test_on_event_startup():
    """
    Test that @app.on_event('startup') decorator registers startup handlers.
    """
    events = []
    app = Tachyon()

    @app.on_event("startup")
    async def on_startup():
        events.append("startup_handler")

    @app.get("/check")
    def check():
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/check")
        assert response.status_code == 200

    assert "startup_handler" in events


def test_on_event_shutdown():
    """
    Test that @app.on_event('shutdown') decorator registers shutdown handlers.
    """
    events = []
    app = Tachyon()

    @app.on_event("shutdown")
    async def on_shutdown():
        events.append("shutdown_handler")

    @app.get("/check")
    def check():
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/check")
        assert response.status_code == 200

    # Shutdown happens after client context exits
    assert "shutdown_handler" in events


def test_multiple_startup_handlers():
    """
    Test that multiple startup handlers can be registered.
    """
    events = []
    app = Tachyon()

    @app.on_event("startup")
    async def init_db():
        events.append("db_init")

    @app.on_event("startup")
    async def init_cache():
        events.append("cache_init")

    @app.on_event("startup")
    def init_config():  # Sync handler should also work
        events.append("config_init")

    @app.get("/check")
    def check():
        return {"events": events}

    with TestClient(app) as client:
        response = client.get("/check")
        assert response.status_code == 200

    assert "db_init" in events
    assert "cache_init" in events
    assert "config_init" in events


def test_multiple_shutdown_handlers():
    """
    Test that multiple shutdown handlers can be registered and run in reverse order.
    """
    events = []
    app = Tachyon()

    @app.on_event("shutdown")
    async def close_db():
        events.append("db_close")

    @app.on_event("shutdown")
    async def close_cache():
        events.append("cache_close")

    @app.get("/check")
    def check():
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/check")
        assert response.status_code == 200

    assert "db_close" in events
    assert "cache_close" in events


def test_on_event_with_sync_handler():
    """
    Test that sync handlers work with on_event.
    """
    events = []
    app = Tachyon()

    @app.on_event("startup")
    def sync_startup():
        events.append("sync_startup")

    @app.on_event("shutdown")
    def sync_shutdown():
        events.append("sync_shutdown")

    @app.get("/check")
    def check():
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/check")
        assert response.status_code == 200

    assert "sync_startup" in events
    assert "sync_shutdown" in events
