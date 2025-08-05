"""
Updated example demonstrating Router system and Scalar integration
Tachyon API v0.4.0 - New Features Demo
"""

from datetime import datetime

from tachyon_api import Tachyon, Router
from tachyon_api.di import injectable
from tachyon_api.models import Struct
from tachyon_api.openapi import OpenAPIConfig, Info, Contact, License
from tachyon_api.params import Body, Path
from tachyon_api.responses import success_response, not_found_response
import msgspec


# Models
class User(Struct):
    id: int
    name: str
    email: str


class CreateUserRequest(Struct):
    name: str
    email: str


class Item(Struct):
    id: int
    name: str
    price: float
    owner_id: int


# Services
@injectable
class UserService:
    def __init__(self):
        self.users = [
            User(id=1, name="Alice", email="alice@example.com"),
            User(id=2, name="Bob", email="bob@example.com"),
        ]

    def get_all_users(self):
        return self.users

    def get_user_by_id(self, user_id: int):
        return next((user for user in self.users if user.id == user_id), None)

    def create_user(self, user_data: CreateUserRequest):
        new_id = max(user.id for user in self.users) + 1 if self.users else 1
        new_user = User(id=new_id, name=user_data.name, email=user_data.email)
        self.users.append(new_user)
        return new_user


@injectable
class ItemService:
    def __init__(self):
        self.items = [
            Item(id=1, name="Laptop", price=999.99, owner_id=1),
            Item(id=2, name="Phone", price=599.99, owner_id=2),
        ]

    def get_items_by_owner(self, owner_id: int):
        return [item for item in self.items if item.owner_id == owner_id]


# Configure OpenAPI with Scalar as default
openapi_config = OpenAPIConfig(
    info=Info(
        title="Tachyon API v0.4.0 Demo",
        description="Demonstrating Router system and Scalar integration",
        version="0.4.0",
        contact=Contact(
            name="Tachyon Team", email="info@tachyon.dev", url="https://tachyon.dev"
        ),
        license=License(
            name="GPL-3.0", url="https://www.gnu.org/licenses/gpl-3.0.html"
        ),
    ),
    # Scalar is now the default for /docs
    # Swagger UI available at /swagger
    # ReDoc available at /redoc
)

# Create main application
app = Tachyon(openapi_config=openapi_config)

# Create routers for different resource groups
users_router = Router(prefix="/api/v1/users", tags=["users"])
items_router = Router(prefix="/api/v1/items", tags=["items"])
admin_router = Router(prefix="/admin", tags=["admin", "management"])


# Users router endpoints
@users_router.get(
    "/", summary="Get all users", description="Retrieve a list of all users"
)
def get_users(user_service: UserService):  # ✅ Inyección implícita
    users = user_service.get_all_users()
    # Convert Struct objects to dicts for JSON serialization
    users_data = [msgspec.to_builtins(user) for user in users]
    return success_response(data=users_data, message="Users retrieved successfully")


@users_router.get("/{user_id}", summary="Get user by ID")
def get_user(
    user_service: UserService,  # ✅ Inyección implícita PRIMERO
    user_id: int = Path(
        description="The ID of the user to retrieve"
    ),  # Path param después
):
    user = user_service.get_user_by_id(user_id)
    if not user:
        return not_found_response("User not found")
    # Convert Struct to dict for JSON serialization
    user_data = msgspec.to_builtins(user)
    return success_response(data=user_data)


@users_router.post("/", summary="Create new user")
def create_user(
    user_service: UserService,  # ✅ Inyección implícita PRIMERO
    user_data: CreateUserRequest = Body(),  # Body param después
):
    new_user = user_service.create_user(user_data)
    # Convert Struct to dict for JSON serialization
    new_user_data = msgspec.to_builtins(new_user)
    return success_response(
        data=new_user_data, message="User created successfully", status_code=201
    )


# Items router endpoints
@items_router.get("/by-owner/{owner_id}", summary="Get items by owner")
def get_items_by_owner(
    user_service: UserService,  # ✅ Inyección implícita PRIMERO
    item_service: ItemService,  # ✅ Inyección implícita PRIMERO
    owner_id: int = Path(description="The ID of the owner"),  # Path param después
):
    # Verify owner exists
    owner = user_service.get_user_by_id(owner_id)
    if not owner:
        return not_found_response("Owner not found")

    items = item_service.get_items_by_owner(owner_id)
    # Convert Struct objects to dicts for JSON serialization
    owner_data = msgspec.to_builtins(owner)
    items_data = [msgspec.to_builtins(item) for item in items]

    return success_response(
        data={"owner": owner_data, "items": items_data},
        message=f"Items for {owner.name} retrieved successfully",
    )


# Admin router endpoints
@admin_router.get("/stats", summary="Get system statistics")
def get_stats(
    user_service: UserService,  # ✅ Inyección implícita
    item_service: ItemService,  # ✅ Inyección implícita
):
    return success_response(
        data={
            "total_users": len(user_service.users),
            "total_items": len(item_service.items),
            "timestamp": datetime.now().isoformat(),
        }
    )


# Include all routers in the main app
app.include_router(users_router)
app.include_router(items_router)
app.include_router(admin_router)


# Root endpoint (directly on main app)
@app.get("/", summary="API Health Check")
def root():
    return success_response(
        data={"status": "healthy", "version": "0.4.0"},
        message="Tachyon API is running!",
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting Tachyon API v0.4.0 Demo")
    print("📚 Documentation available at:")
    print("  • Scalar (new default): http://localhost:8000/docs")
    print("  • Swagger UI (legacy):   http://localhost:8000/swagger")
    print("  • ReDoc:                 http://localhost:8000/redoc")
    print("📋 API Endpoints:")
    print("  • GET  /")
    print("  • GET  /health")
    print("  • GET  /api/v1/users/")
    print("  • GET  /api/v1/users/{user_id}")
    print("  • POST /api/v1/users/")
    print("  • GET  /api/v1/items/by-owner/{owner_id}")
    print("  • GET  /admin/stats")

    uvicorn.run(app, host="0.0.0.0", port=8000)
