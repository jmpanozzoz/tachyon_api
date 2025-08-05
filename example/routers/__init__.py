"""
Routers package for organizing API endpoints
"""

from .users import users_router
from .items import items_router
from .admin import admin_router

__all__ = ["users_router", "items_router", "admin_router"]
