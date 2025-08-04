from tachyon_api.models import Struct


class Item(Struct):
    """
    Item model for the training example

    Demonstrates:
    - Basic Struct model definition
    - Type annotations for validation
    - Optional fields with defaults
    """
    id: int
    name: str
    description: str = "No description provided"
