from typing import List, Optional
from tachyon_api.di import injectable
from example.models.item import Item


@injectable
class ItemRepository:
    """
    Item repository for data access - Training Example

    Demonstrates:
    - Repository pattern implementation
    - In-memory data storage for simplicity
    - CRUD operations
    - Error handling for duplicates
    """

    def __init__(self):
        # Mock data for training purposes
        self._items = [
            Item(id=1, name="Laptop", description="High-performance gaming laptop"),
            Item(id=2, name="Mouse", description="Wireless optical mouse"),
            Item(
                id=3,
                name="Keyboard",
                description="Mechanical keyboard with RGB lighting",
            ),
            Item(id=4, name="Monitor", description="4K UHD display monitor"),
            Item(
                id=5,
                name="Headphones",
                description="Noise-cancelling wireless headphones",
            ),
        ]
        self._next_id = 6

    def get_all(self) -> List[Item]:
        """Get all items"""
        return self._items.copy()

    def get_by_id(self, item_id: int) -> Optional[Item]:
        """Get item by ID"""
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def create(self, item_data: Item) -> Item:
        """
        Create a new item

        Raises:
            ValueError: If an item with the same name already exists
        """
        # Check for duplicate names (for training purposes)
        existing_names = [item.name.lower() for item in self._items]
        if item_data.name.lower() in existing_names:
            raise ValueError(f"Item with name '{item_data.name}' already exists")

        # Create new item with auto-generated ID
        new_item = Item(
            id=self._next_id, name=item_data.name, description=item_data.description
        )

        self._items.append(new_item)
        self._next_id += 1

        return new_item

    def update(self, item_id: int, item_data: Item) -> Optional[Item]:
        """Update an existing item"""
        for i, item in enumerate(self._items):
            if item.id == item_id:
                updated_item = Item(
                    id=item_id, name=item_data.name, description=item_data.description
                )
                self._items[i] = updated_item
                return updated_item
        return None

    def delete(self, item_id: int) -> bool:
        """Delete an item by ID"""
        for i, item in enumerate(self._items):
            if item.id == item_id:
                del self._items[i]
                return True
        return False
