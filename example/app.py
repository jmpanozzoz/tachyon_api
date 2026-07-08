"""
KYC Demo API — Tachyon showcase, fully exercised by its test suite.

Demonstrates:

  - Dependency injection with `@injectable` + `Depends(callable)`
  - JWT auth via a callable dependency (see `auth_controller.py`)
  - `SecurityHeadersMiddleware` opt-in (this file)
  - `@app.exception_handler` with custom error type (this file)
  - `BackgroundTasks` for fire-and-forget work (see `verification_controller.py`)
  - WebSocket notifications fed by the verification flow (this file)
  - Lifespan startup/shutdown (this file)
  - Async test client `create_client` (see `tests/test_async_client.py`)

Run:
    poetry run uvicorn example.app:app --reload --loop uvloop
"""

from contextlib import asynccontextmanager

from starlette.requests import Request
from starlette.responses import JSONResponse

from tachyon_api import Tachyon
from tachyon_api.middlewares import (
    CORSMiddleware,
    LoggerMiddleware,
    SecurityHeadersMiddleware,
)
from tachyon_api.openapi import Info, OpenAPIConfig

from .config import settings
from .shared.exceptions import KYCException
from .shared.websocket_manager import manager as ws_manager

# Module routers
from .modules.auth import router as auth_router
from .modules.customers import router as customers_router
from .modules.verification import router as verification_router


@asynccontextmanager
async def lifespan(app):
    """Startup: connect DB, init clients, load models. Shutdown: cleanup."""
    print("🚀 KYC API Starting...")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")

    app.state.settings = settings
    app.state.ws_manager = ws_manager

    # Mock: simulate connecting to a verification provider
    app.state.verification_provider = "MockVerificationProvider"
    print("   ✅ Verification provider connected")

    yield

    print("🛑 KYC API Shutting down...")
    await ws_manager.disconnect_all()
    print("   ✅ All WebSocket connections closed")


# ── App + OpenAPI config ──────────────────────────────────────────────────────

openapi_config = OpenAPIConfig(
    info=Info(
        title="KYC Demo API",
        description=(
            "Know Your Customer verification system — built on Tachyon. "
            "Showcases DI, JWT auth, security headers, background tasks, "
            "custom exception handlers, WebSockets, and the testing helpers."
        ),
        version="1.3.0",
    )
)

app = Tachyon(
    openapi_config=openapi_config,
    lifespan=lifespan,
)


# ── Middlewares ───────────────────────────────────────────────────────────────
# Order matters: outermost wrappers go first in the source, but ASGI calls them
# in reverse — so the last `add_middleware` is the innermost.

app.add_middleware(
    SecurityHeadersMiddleware,
    # Pass explicit values when defaults need to be tightened or relaxed for
    # this deployment. The defaults applied below are the same Tachyon ships,
    # listed here for documentation visibility.
    x_content_type_options="nosniff",
    x_frame_options="DENY",
    referrer_policy="strict-origin-when-cross-origin",
    # hsts and csp are opt-in — they need site-specific configuration.
    # Example: hsts="max-age=63072000; includeSubDomains"
)

app.add_middleware(
    CORSMiddleware,
    # v1.2.0 changed CORS defaults to opt-in (no more wildcard).  We list the
    # origins this demo accepts.  Production should never use "*".
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    allow_credentials=True,
)

app.add_middleware(LoggerMiddleware)


# ── Custom exception handler ──────────────────────────────────────────────────

@app.exception_handler(KYCException)
async def kyc_exception_handler(request: Request, exc: KYCException) -> JSONResponse:
    """
    Single handler for the whole KYCException hierarchy.

    Translates the domain-specific `error_code` into the response body while
    preserving the HTTP status code declared by the exception.  Other HTTPException
    types raised by the framework fall through to Tachyon's default
    `{"detail": ...}` response.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "code": getattr(exc, "error_code", "KYC_ERROR"),
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(customers_router)
app.include_router(verification_router)


# ── Top-level health endpoints ────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "KYC Demo API",
        "version": "1.3.0",
        "framework": "tachyon-api",
    }


@app.get("/health", tags=["Health"])
def detailed_health():
    return {
        "status": "healthy",
        "components": {
            "api": "up",
            "database": "up (mock)",
            "verification_provider": "up (mock)",
            "websocket": "up",
        },
        "environment": settings.environment,
    }


# ── Customer notification WebSocket ──────────────────────────────────────────
# Consumer side of the verification flow: process_verification() broadcasts
# status updates through ws_manager to clients connected here.

@app.websocket("/ws/notifications/{customer_id}")
async def websocket_notifications(websocket, customer_id: str):
    """Real-time KYC status updates via WebSocket — customer-facing channel."""
    await ws_manager.connect(websocket, customer_id)

    try:
        await websocket.send_json({
            "type": "connected",
            "message": f"Connected to KYC notifications for customer {customer_id}",
        })

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket, customer_id)
