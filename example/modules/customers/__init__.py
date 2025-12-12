"""
Customers Module - Customer management.

Features:
- Create customer profiles
- Update customer information
- Get customer details
- List customers (admin)
"""

from .customers_controller import router

__all__ = ["router"]
