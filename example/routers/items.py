"""
Items router - API endpoints for item management
"""

import msgspec
from tachyon_api import Router
from tachyon_api.params import Path
from tachyon_api.responses import success_response, not_found_response
from example.services.item import ItemService
from example.services.user import UserService

# Create items router with prefix and tags
items_router = Router(prefix="/api/v1/items", tags=["items"])


@items_router.get("/by-owner/{owner_id}", summary="Get items by owner")
def get_items_by_owner(
    user_service: UserService,  # Implicit dependency injection FIRST
    item_service: ItemService,  # Implicit dependency injection FIRST
    owner_id: int = Path(description="The ID of the owner"),
):
    """Get all items belonging to a specific owner"""
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
