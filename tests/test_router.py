"""
Tests for Tachyon Router functionality

This module tests the router grouping functionality similar to FastAPI's APIRouter,
allowing for better organization of routes with common prefixes, tags, and dependencies.
"""

from starlette.testclient import TestClient

from tachyon_api import Tachyon
from tachyon_api.router import Router
from tachyon_api.models import Struct
from tachyon_api.params import Query, Path, Body
from tachyon_api.di import injectable, Depends


class TestBasicRouter:
    """Test basic router functionality"""

    def test_router_creation(self):
        """Test that Router can be created with default settings"""
        router = Router()
        assert router is not None
        assert router.prefix == ""
        assert router.tags == []

    def test_router_creation_with_prefix(self):
        """Test Router creation with prefix"""
        router = Router(prefix="/api/v1")
        assert router.prefix == "/api/v1"

    def test_router_creation_with_tags(self):
        """Test Router creation with tags"""
        router = Router(tags=["users", "admin"])
        assert router.tags == ["users", "admin"]

    def test_router_creation_with_prefix_and_tags(self):
        """Test Router creation with both prefix and tags"""
        router = Router(prefix="/api/v1", tags=["users"])
        assert router.prefix == "/api/v1"
        assert router.tags == ["users"]


class TestRouterDecorators:
    """Test router HTTP method decorators"""

    def test_router_has_http_method_decorators(self):
        """Test that router has all HTTP method decorators"""
        router = Router()

        # Check that all HTTP method decorators exist
        assert hasattr(router, "get")
        assert hasattr(router, "post")
        assert hasattr(router, "put")
        assert hasattr(router, "delete")
        assert hasattr(router, "patch")
        assert hasattr(router, "options")
        assert hasattr(router, "head")

    def test_router_decorators_are_callable(self):
        """Test that router decorators are callable"""
        router = Router()

        # Test that decorators can be called
        @router.get("/test")
        def test_endpoint():
            return {"message": "test"}

        assert test_endpoint is not None

    def test_router_stores_routes(self):
        """Test that router stores registered routes"""
        router = Router()

        @router.get("/users")
        def get_users():
            return {"users": []}

        @router.post("/users")
        def create_user():
            return {"user": "created"}

        # Router should store the routes
        assert len(router.routes) == 2
        assert any(
            route["path"] == "/users" and route["method"] == "GET"
            for route in router.routes
        )
        assert any(
            route["path"] == "/users" and route["method"] == "POST"
            for route in router.routes
        )


class TestRouterIncludeInApp:
    """Test including routers in main application"""

    def test_include_router_basic(self):
        """Test basic router inclusion"""
        app = Tachyon()
        router = Router()

        @router.get("/health")
        def health_check():
            return {"status": "ok"}

        # App should have include_router method
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_include_router_with_prefix(self):
        """Test router inclusion with prefix"""
        app = Tachyon()
        router = Router(prefix="/api/v1")

        @router.get("/users")
        def get_users():
            return {"users": []}

        app.include_router(router)

        client = TestClient(app)
        # Should be accessible with prefix
        response = client.get("/api/v1/users")
        assert response.status_code == 200
        assert response.json() == {"users": []}

        # Should not be accessible without prefix
        response = client.get("/users")
        assert response.status_code == 404

    def test_include_multiple_routers(self):
        """Test including multiple routers"""
        app = Tachyon()

        users_router = Router(prefix="/users")
        items_router = Router(prefix="/items")

        @users_router.get("/")
        def get_users():
            return {"users": []}

        @items_router.get("/")
        def get_items():
            return {"items": []}

        app.include_router(users_router)
        app.include_router(items_router)

        client = TestClient(app)

        response = client.get("/users/")
        assert response.status_code == 200
        assert response.json() == {"users": []}

        response = client.get("/items/")
        assert response.status_code == 200
        assert response.json() == {"items": []}


class TestRouterWithParameters:
    """Test router with various parameter types"""

    def test_router_with_path_parameters(self):
        """Test router routes with path parameters"""
        app = Tachyon()
        router = Router(prefix="/users")

        @router.get("/{user_id}")
        def get_user(user_id: int = Path()):
            return {"user_id": user_id}

        app.include_router(router)

        client = TestClient(app)
        response = client.get("/users/123")
        assert response.status_code == 200
        assert response.json() == {"user_id": 123}

    def test_router_with_query_parameters(self):
        """Test router routes with query parameters"""
        app = Tachyon()
        router = Router(prefix="/api")

        @router.get("/search")
        def search(q: str = Query(), limit: int = Query(default=10)):
            return {"query": q, "limit": limit}

        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/search?q=test&limit=5")
        assert response.status_code == 200
        assert response.json() == {"query": "test", "limit": 5}

    def test_router_with_body_parameters(self):
        """Test router routes with request body"""
        app = Tachyon()
        router = Router(prefix="/api")

        class CreateUserRequest(Struct):
            name: str
            email: str

        @router.post("/users")
        def create_user(user_data: CreateUserRequest = Body()):
            return {"name": user_data.name, "email": user_data.email}

        app.include_router(router)

        client = TestClient(app)
        response = client.post(
            "/api/users", json={"name": "John", "email": "john@example.com"}
        )
        assert response.status_code == 200
        assert response.json() == {"name": "John", "email": "john@example.com"}


class TestRouterWithDependencies:
    """Test router with dependency injection"""

    def test_router_with_dependencies(self):
        """Test router routes with dependencies"""

        @injectable
        class UserService:
            def get_current_user(self):
                return {"id": 1, "name": "Test User"}

        app = Tachyon()
        router = Router(prefix="/protected")

        @router.get("/profile")
        def get_profile(user_service: UserService = Depends()):
            return user_service.get_current_user()

        app.include_router(router)

        client = TestClient(app)
        response = client.get("/protected/profile")
        assert response.status_code == 200
        assert response.json() == {"id": 1, "name": "Test User"}

    def test_router_with_common_dependencies(self):
        """Test router with common dependencies applied to all routes"""

        @injectable
        class AuthService:
            def authenticate(self):
                return {"authenticated": True}

        # This test will be implemented when we add common dependencies support
        # For now, we'll test the structure
        router = Router(prefix="/admin", dependencies=[Depends()])
        assert router.dependencies is not None


class TestRouterTags:
    """Test router tags functionality"""

    def test_router_tags_applied_to_routes(self):
        """Test that router tags are applied to all routes"""
        app = Tachyon()
        router = Router(prefix="/users", tags=["users", "management"])

        @router.get("/")
        def get_users():
            return {"users": []}

        @router.post("/")
        def create_user():
            return {"user": "created"}

        app.include_router(router)

        # Check that routes have the correct tags in OpenAPI schema
        openapi_schema = app.openapi_generator.get_openapi_schema()

        # All routes should have the router tags
        for path_data in openapi_schema["paths"].values():
            for operation in path_data.values():
                if "tags" in operation:
                    assert "users" in operation["tags"]
                    assert "management" in operation["tags"]


class TestRouterOpenAPIIntegration:
    """Test router integration with OpenAPI documentation"""

    def test_router_routes_in_openapi_schema(self):
        """Test that router routes appear in OpenAPI schema"""
        app = Tachyon()
        router = Router(prefix="/api/v1")

        @router.get("/status")
        def get_status():
            return {"status": "running"}

        app.include_router(router)

        # Trigger OpenAPI schema generation by accessing it
        openapi_schema = app.openapi_generator.get_openapi_schema()

        # Check that the route appears with the correct prefix
        assert "/api/v1/status" in openapi_schema["paths"]
        assert "get" in openapi_schema["paths"]["/api/v1/status"]

    def test_router_with_custom_route_metadata(self):
        """Test router routes with custom OpenAPI metadata"""
        app = Tachyon()
        router = Router(prefix="/api")

        @router.get(
            "/users",
            summary="Get all users",
            description="Retrieve a list of all users",
        )
        def get_users():
            return {"users": []}

        app.include_router(router)

        openapi_schema = app.openapi_generator.get_openapi_schema()
        operation = openapi_schema["paths"]["/api/users"]["get"]

        assert operation["summary"] == "Get all users"
        assert operation["description"] == "Retrieve a list of all users"


class TestRouterErrorHandling:
    """Test router error handling"""

    def test_invalid_prefix_handling(self):
        """Test handling of invalid prefixes"""
        # Should handle prefixes without leading slash
        router = Router(prefix="api/v1")
        # Should normalize to /api/v1
        assert router.prefix == "/api/v1"

        # Should handle empty string
        router = Router(prefix="")
        assert router.prefix == ""

        # Should handle None
        router = Router(prefix=None)
        assert router.prefix == ""

    def test_duplicate_route_handling(self):
        """Test handling of duplicate routes in router"""
        router = Router()

        @router.get("/test")
        def test1():
            return {"test": 1}

        @router.get("/test")
        def test2():
            return {"test": 2}

        # Should allow duplicate routes (last one wins, like FastAPI)
        assert len(router.routes) == 2
