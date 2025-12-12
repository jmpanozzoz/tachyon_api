"""
🏦 KYC Demo API - Know Your Customer Verification System

This example demonstrates all Tachyon features:
- Clean Architecture (Controllers, Services, Repositories)
- Dependency Injection (@injectable, Depends)
- Authentication (JWT Bearer, API Keys)
- File Uploads (Document verification)
- Background Tasks (Async verification processing)
- WebSockets (Real-time status updates)
- Caching (Verification results)
- Exception Handling (Custom exceptions)
- Lifecycle Events (Startup/Shutdown)
- Testing Utilities (Mocks, Overrides)

Run with: uvicorn example.app:app --reload
"""

from contextlib import asynccontextmanager

from tachyon_api import Tachyon, AsgiEngine
from tachyon_api.middlewares import CORSMiddleware, LoggerMiddleware
from tachyon_api.openapi import OpenAPIConfig, Info

# Note: Tachyon v1.0.0 supports engine selection:
# - AsgiEngine.STARLETTE (default, stable)
# - AsgiEngine.TACHYON (experimental, requires tachyon-engine v0.2.0+)
# Example: app = Tachyon(..., engine=AsgiEngine.TACHYON)

from .config import settings
from .shared.websocket_manager import manager as ws_manager

# Import routers
from .modules.auth import router as auth_router
from .modules.customers import router as customers_router
from .modules.verification import router as verification_router
from .modules.documents import router as documents_router


@asynccontextmanager
async def lifespan(app):
    """
    Application lifespan - startup and shutdown events.
    
    In production, you would:
    - Connect to databases
    - Initialize external service clients
    - Load ML models for document verification
    """
    print("🚀 KYC API Starting...")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")
    
    # Initialize app state
    app.state.settings = settings
    app.state.ws_manager = ws_manager
    
    # Mock: Simulate connecting to verification provider
    app.state.verification_provider = "MockVerificationProvider"
    print("   ✅ Verification provider connected")
    
    yield
    
    # Cleanup
    print("🛑 KYC API Shutting down...")
    await ws_manager.disconnect_all()
    print("   ✅ All WebSocket connections closed")


# Create app
openapi_config = OpenAPIConfig(
    info=Info(
        title="KYC Demo API",
        description="Know Your Customer verification system demo using Tachyon",
        version="1.0.0",
    )
)

app = Tachyon(
    openapi_config=openapi_config,
    lifespan=lifespan,
)

# Add middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggerMiddleware)

# Register routers
app.include_router(auth_router)
app.include_router(customers_router)
app.include_router(verification_router)
app.include_router(documents_router)


# Health check
@app.get("/", tags=["Health"])
def health_check():
    """
    Health check endpoint.
    
    Returns the API status and version.
    """
    return {
        "status": "healthy",
        "service": "KYC Demo API",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
def detailed_health():
    """
    Detailed health check with component status.
    """
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


# WebSocket for real-time notifications
@app.websocket("/ws/notifications/{customer_id}")
async def websocket_notifications(websocket, customer_id: str):
    """
    WebSocket endpoint for real-time KYC status updates.
    
    Clients connect here to receive instant notifications
    when their verification status changes.
    """
    await ws_manager.connect(websocket, customer_id)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": f"Connected to KYC notifications for customer {customer_id}",
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_json()
            
            # Handle ping/pong for keep-alive
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket, customer_id)
