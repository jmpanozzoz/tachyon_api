"""
Item models for the Tachyon API v0.4.0 Demo
"""

from tachyon_api.models import Struct


class Item(Struct):
    """Item model"""

    id: int
    name: str
    price: float
    owner_id: int
