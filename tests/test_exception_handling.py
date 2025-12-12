"""
Tests for HTTPException and custom exception handlers (TDD).
Release 0.6.3 - Exception Handling
"""

import pytest
from httpx import AsyncClient, ASGITransport


# =============================================================================
# HTTPException Tests
# =============================================================================

@pytest.mark.asyncio
async def test_http_exception_basic():
    """HTTPException should return correct status and detail."""
    from tachyon_api import Tachyon, HTTPException

    app = Tachyon()

    @app.get("/error")
    def raise_error():
        raise HTTPException(status_code=404, detail="Item not found")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/error")
        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found"}


@pytest.mark.asyncio
async def test_http_exception_401_unauthorized():
    """HTTPException with 401 status code."""
    from tachyon_api import Tachyon, HTTPException

    app = Tachyon()

    @app.get("/protected")
    def protected():
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/protected")
        assert response.status_code == 401
        assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_http_exception_403_forbidden():
    """HTTPException with 403 status code."""
    from tachyon_api import Tachyon, HTTPException

    app = Tachyon()

    @app.get("/admin")
    def admin_only():
        raise HTTPException(status_code=403, detail="Forbidden")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/admin")
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}


@pytest.mark.asyncio
async def test_http_exception_with_headers():
    """HTTPException can include custom headers."""
    from tachyon_api import Tachyon, HTTPException

    app = Tachyon()

    @app.get("/auth")
    def need_auth():
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/auth")
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert response.json() == {"detail": "Authentication required"}


@pytest.mark.asyncio
async def test_http_exception_500_server_error():
    """HTTPException with 500 status code."""
    from tachyon_api import Tachyon, HTTPException

    app = Tachyon()

    @app.get("/fail")
    def server_fail():
        raise HTTPException(status_code=500, detail="Internal error")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/fail")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal error"}


# =============================================================================
# Custom Exception Handler Tests
# =============================================================================

@pytest.mark.asyncio
async def test_custom_exception_handler_decorator():
    """@app.exception_handler should register custom handler."""
    from tachyon_api import Tachyon

    app = Tachyon()

    class CustomError(Exception):
        def __init__(self, message: str):
            self.message = message

    @app.exception_handler(CustomError)
    async def handle_custom_error(request, exc):
        from tachyon_api.responses import JSONResponse
        return JSONResponse(
            status_code=418,
            content={"custom_error": exc.message}
        )

    @app.get("/custom")
    def raise_custom():
        raise CustomError("Something went wrong")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/custom")
        assert response.status_code == 418
        assert response.json() == {"custom_error": "Something went wrong"}


@pytest.mark.asyncio
async def test_custom_exception_handler_sync():
    """Sync exception handlers should also work."""
    from tachyon_api import Tachyon
    from tachyon_api.responses import JSONResponse

    app = Tachyon()

    class ValidationError(Exception):
        pass

    @app.exception_handler(ValidationError)
    def handle_validation(request, exc):
        return JSONResponse(
            status_code=400,
            content={"error": "Validation failed"}
        )

    @app.get("/validate")
    def validate():
        raise ValidationError()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/validate")
        assert response.status_code == 400
        assert response.json() == {"error": "Validation failed"}


@pytest.mark.asyncio
async def test_exception_handler_receives_request():
    """Exception handler should receive the request object."""
    from tachyon_api import Tachyon
    from tachyon_api.responses import JSONResponse

    app = Tachyon()

    class PathError(Exception):
        pass

    @app.exception_handler(PathError)
    async def handle_path_error(request, exc):
        return JSONResponse(
            status_code=500,
            content={"path": str(request.url.path)}
        )

    @app.get("/test-path")
    def test_path():
        raise PathError()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/test-path")
        assert response.status_code == 500
        assert response.json() == {"path": "/test-path"}


@pytest.mark.asyncio
async def test_multiple_exception_handlers():
    """Multiple exception types can have different handlers."""
    from tachyon_api import Tachyon
    from tachyon_api.responses import JSONResponse

    app = Tachyon()

    class ErrorA(Exception):
        pass

    class ErrorB(Exception):
        pass

    @app.exception_handler(ErrorA)
    async def handle_a(request, exc):
        return JSONResponse(status_code=400, content={"type": "A"})

    @app.exception_handler(ErrorB)
    async def handle_b(request, exc):
        return JSONResponse(status_code=401, content={"type": "B"})

    @app.get("/error-a")
    def raise_a():
        raise ErrorA()

    @app.get("/error-b")
    def raise_b():
        raise ErrorB()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp_a = await client.get("/error-a")
        assert resp_a.status_code == 400
        assert resp_a.json() == {"type": "A"}

        resp_b = await client.get("/error-b")
        assert resp_b.status_code == 401
        assert resp_b.json() == {"type": "B"}


@pytest.mark.asyncio
async def test_override_http_exception_handler():
    """HTTPException handler can be overridden."""
    from tachyon_api import Tachyon, HTTPException
    from tachyon_api.responses import JSONResponse

    app = Tachyon()

    @app.exception_handler(HTTPException)
    async def custom_http_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "custom": True}
        )

    @app.get("/not-found")
    def not_found():
        raise HTTPException(status_code=404, detail="Not found")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/not-found")
        assert response.status_code == 404
        assert response.json() == {"error": "Not found", "custom": True}


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500():
    """Unhandled exceptions should still return 500."""
    from tachyon_api import Tachyon

    app = Tachyon()

    @app.get("/crash")
    def crash():
        raise RuntimeError("Unexpected error")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/crash")
        assert response.status_code == 500
