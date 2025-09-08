"""
Admin router - API endpoints for system administration
"""

from datetime import datetime
from tachyon_api import Router
from tachyon_api.schemas.responses import success_response
from example.services.user import UserService
from example.services.item import ItemService

# Create admin router with prefix and tags
admin_router = Router(prefix="/admin", tags=["admin", "management"])


@admin_router.get("/stats", summary="Get system statistics")
def get_stats(
    user_service: UserService,  # Implicit dependency injection
    item_service: ItemService,  # Implicit dependency injection
):
    """Get system statistics and metrics"""
    return success_response(
        data={
            "total_users": len(user_service.get_all_users()),
            "total_items": len(item_service.get_all_items()),
            "timestamp": datetime.now().isoformat(),
        }
    )
