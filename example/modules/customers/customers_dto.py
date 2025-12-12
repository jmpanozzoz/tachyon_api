"""
Customers DTOs - Data Transfer Objects for customer management.
"""

from typing import Optional, List
from tachyon_api import Struct


class AddressDTO(Struct):
    """Customer address information."""
    
    street: str
    city: str
    state: str
    postal_code: str
    country: str


class CustomerCreate(Struct):
    """Request body for creating a customer."""
    
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None  # YYYY-MM-DD
    address: Optional[AddressDTO] = None


class CustomerUpdate(Struct):
    """Request body for updating a customer."""
    
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[AddressDTO] = None


class CustomerResponse(Struct):
    """Customer information response."""
    
    customer_id: str
    user_id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[AddressDTO] = None
    kyc_status: str = "pending"  # pending, in_progress, verified, rejected
    created_at: str = ""
    updated_at: str = ""


class CustomerListResponse(Struct):
    """Paginated list of customers."""
    
    customers: List[CustomerResponse]
    total: int
    page: int
    limit: int
