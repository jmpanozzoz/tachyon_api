"""
Users router - API endpoints for user management
"""

import msgspec
from tachyon_api import Router
from tachyon_api.params import Body, Path
from tachyon_api.responses import success_response, not_found_response
from example.models.user import CreateUserRequest
from example.services.user import UserService

# Create users router with prefix and tags
users_router = Router(prefix="/api/v1/users", tags=["users"])


@users_router.get(
    "/", summary="Get all users", description="Retrieve a list of all users"
)
def get_users(user_service: UserService):
    """Get all users using implicit dependency injection"""
    users = user_service.get_all_users()
    # Convert Struct objects to dicts for JSON serialization
    users_data = [msgspec.to_builtins(user) for user in users]
    return success_response(data=users_data, message="Users retrieved successfully")


@users_router.get("/{user_id}", summary="Get user by ID")
def get_user(
    user_service: UserService,  # Implicit dependency injection FIRST
    user_id: int = Path(description="The ID of the user to retrieve"),
):
    """Get a specific user by ID"""
    user = user_service.get_user_by_id(user_id)
    if not user:
        return not_found_response("User not found")

    # Convert Struct to dict for JSON serialization
    user_data = msgspec.to_builtins(user)
    return success_response(data=user_data)


@users_router.post("/", summary="Create new user")
def create_user(
    user_service: UserService,  # Implicit dependency injection FIRST
    user_data: CreateUserRequest = Body(),
):
    """Create a new user"""
    new_user = user_service.create_user(user_data)
    # Convert Struct to dict for JSON serialization
    new_user_data = msgspec.to_builtins(new_user)
    return success_response(
        data=new_user_data, message="User created successfully", status_code=201
    )
