"""
Tachyon API v0.6.0 Demo - Complete Example Application

This example demonstrates:
- Router system with organized endpoints
- Scalar API Reference as default documentation
- Implicit dependency injection
- Clean architecture with services, repositories, and models
- Complete CRUD operations with proper error handling
- Middleware implementation for logging and response modification
- Cache decorator with TTL and configurable backends
- Starlette-Native Architecture
"""

from datetime import datetime
from tachyon_api import Tachyon, cache, create_cache_config
from tachyon_api.openapi import OpenAPIConfig, Info, Contact, License
from tachyon_api.schemas.responses import success_response
from tachyon_api.middlewares import CORSMiddleware, LoggerMiddleware

# Import all routers
from example.routers import users_router, items_router, admin_router

# Import middleware setup
from example.middlewares import setup_middlewares

# Configure OpenAPI with Scalar as default
openapi_config = OpenAPIConfig(
    info=Info(
        title="Tachyon API Demo",
        description="Complete example demonstrating Router system, Scalar integration, caching, and clean architecture",
        version="0.5.6",
        contact=Contact(
            name="Tachyon Team", email="info@tachyon.dev", url="https://tachyon.dev"
        ),
        license=License(
            name="GPL-3.0", url="https://www.gnu.org/licenses/gpl-3.0.html"
        ),
    ),
)

# Configure Cache (default: in-memory backend); can be replaced by Redis/Memcached adapters
cache_config = create_cache_config(default_ttl=30)

# Create main application
app = Tachyon(openapi_config=openapi_config, cache_config=cache_config)

# Built-in middlewares (class-based)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)
app.add_middleware(
    LoggerMiddleware,
    include_headers=False,  # set True to log headers
)

# Set up additional example middlewares using the decorator pattern
setup_middlewares(app)

# Include all routers in the main app
app.include_router(users_router)
app.include_router(items_router)
app.include_router(admin_router)


# Root endpoints (directly on main app)
@app.get("/", summary="API Health Check")
def root():
    """Root endpoint for API health check"""
    return success_response(
        data={
            "status": "healthy",
            "version": "0.4.0",
            "timestamp": datetime.now().isoformat(),
            "message": "Tachyon API is running!",
        }
    )


@app.get("/health")
def health_check():
    """Simple health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/orjson-demo", summary="Default JSON serialization demo")
def orjson_demo():
    """Demonstrate default TachyonJSONResponse serializing complex types."""
    import uuid

    return {
        "uuid": uuid.uuid4(),
        "today": datetime.now().date(),
    }


# Cached endpoint demo (value remains constant within TTL)
@app.get("/cached/time", summary="Cached time demo")
@cache(TTL=10)
def cached_time():
    """Return current time, cached for TTL seconds."""
    return {"now": datetime.now().isoformat()}


@app.get("/error-demo", summary="Global exception handler demo")
def error_demo():
    """Demonstrate global exception handling returning a structured 500 without leaking details."""
    raise RuntimeError("simulated failure")


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting Tachyon API v0.6.0 Complete Example")
    print("📁 Clean Architecture:")
    print("  • Models: Data structures and validation")
    print("  • Repositories: Data access layer")
    print("  • Services: Business logic layer")
    print("  • Routers: API endpoint organization")
    print()
    print("📚 Documentation available at:")
    print("  • Scalar (new default): http://localhost:8000/docs")
    print("  • Swagger UI (legacy):   http://localhost:8000/swagger")
    print("  • ReDoc:                 http://localhost:8000/redoc")
    print()
    print("📋 API Endpoints:")
    print("  • GET  /                                 - API Health Check")
    print("  • GET  /health                          - Simple Health Check")
    print("  • GET  /cached/time                     - Cached time (TTL=10s)")
    print(
        "  • GET  /error-demo                      - Global exception handler demo (returns 500)"
    )
    print("  • GET  /api/v1/users/                   - Get All Users")
    print("  • GET  /api/v1/users/{user_id}          - Get User by ID")
    print("  • POST /api/v1/users/                   - Create New User")
    print("  • POST /api/v1/users/e2e                - Create User (end-to-end safety)")
    print("  • GET  /api/v1/items/by-owner/{owner_id} - Get Items by Owner")
    print("  • GET  /admin/stats                     - System Statistics")
    print()
    print("💡 Features demonstrated:")
    print("  ✅ Router system for endpoint organization")
    print("  ✅ Implicit dependency injection (no Depends() needed)")
    print("  ✅ Scalar API Reference (modern documentation)")
    print("  ✅ Clean architecture (Models/Services/Repositories)")
    print("  ✅ Proper error handling and responses")
    print("  ✅ Automatic JSON serialization of Struct models")
    print("  ✅ Cache decorator with TTL and configurable backends")

    uvicorn.run(app, host="0.0.0.0", port=8000)
