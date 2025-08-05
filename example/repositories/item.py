"""
Item repository for data access
"""

from typing import List
from tachyon_api.di import injectable
from example.models.item import Item


@injectable
class ItemRepository:
    """Repository for item data access"""

    def __init__(self):
        # Sample data
        self.items = [
            Item(id=1, name="Laptop", price=999.99, owner_id=1),
            Item(id=2, name="Phone", price=599.99, owner_id=2),
        ]

    def get_by_owner(self, owner_id: int) -> List[Item]:
        """Get items by owner ID"""
        return [item for item in self.items if item.owner_id == owner_id]

    def get_all(self) -> List[Item]:
        """Get all items"""
        return self.items
