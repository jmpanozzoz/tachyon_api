"""
Item service for business logic
"""

from typing import List, Optional, Tuple
from tachyon_api.dependencies.injection import injectable
from example.models.item import Item
from example.repositories.item import ItemRepository


@injectable
class ItemService:
    """Service for item business logic"""

    def __init__(self, item_repo: ItemRepository):
        self.item_repo = item_repo

    def get_items_by_owner(self, owner_id: int) -> List[Item]:
        """Get items by owner ID"""
        return self.item_repo.get_by_owner(owner_id)

    def get_all_items(self) -> List[Item]:
        """Get all items"""
        return self.item_repo.get_all()

    def get_item(self, item_id: int) -> Optional[Item]:
        """
        Get a specific item by ID

        Args:
            item_id: The unique identifier of the item

        Returns:
            Item if found, None otherwise
        """
        return self.item_repo.get_by_id(item_id)

    def create_item(self, item_data: Item) -> Tuple[Optional[Item], Optional[str]]:
        """
        Create a new item with business validation

        Args:
            item_data: Item information to create

        Returns:
            Tuple[Optional[Item], Optional[str]]: (created_item, error_message)
            - Success: (item, None)
            - Error: (None, error_message)
        """
        try:
            # Business validation
            if not item_data.name or len(item_data.name.strip()) < 2:
                return None, "Item name must be at least 2 characters long"

            if len(item_data.name) > 100:
                return None, "Item name cannot exceed 100 characters"

            # Attempt to create
            created_item = self.item_repo.create(item_data)
            return created_item, None

        except ValueError as e:
            # Handle repository-level errors (like duplicates)
            return None, str(e)
        except Exception as e:
            # Handle unexpected errors
            return None, f"Unexpected error creating item: {str(e)}"

    def update_item(
        self, item_id: int, item_data: Item
    ) -> Tuple[Optional[Item], Optional[str]]:
        """
        Update an existing item

        Args:
            item_id: ID of the item to update
            item_data: New item data

        Returns:
            Tuple[Optional[Item], Optional[str]]: (updated_item, error_message)
        """
        try:
            # Business validation
            if not item_data.name or len(item_data.name.strip()) < 2:
                return None, "Item name must be at least 2 characters long"

            # Check if item exists
            existing_item = self.item_repo.get_by_id(item_id)
            if not existing_item:
                return None, f"Item with ID {item_id} not found"

            # Update
            updated_item = self.item_repo.update(item_id, item_data)
            return updated_item, None

        except Exception as e:
            return None, f"Error updating item: {str(e)}"

    def delete_item(self, item_id: int) -> Tuple[bool, Optional[str]]:
        """
        Delete an item

        Args:
            item_id: ID of the item to delete

        Returns:
            Tuple[bool, Optional[str]]: (success, error_message)
        """
        try:
            # Check if item exists
            existing_item = self.item_repo.get_by_id(item_id)
            if not existing_item:
                return False, f"Item with ID {item_id} not found"

            # Delete
            success = self.item_repo.delete(item_id)
            return success, None

        except Exception as e:
            return False, f"Error deleting item: {str(e)}"
