"""
Customers Service - Business logic for customer management.
"""

from typing import Optional

from tachyon_api import injectable

from ...shared.exceptions import CustomerNotFoundError
from .customers_repository import CustomersRepository
from .customers_dto import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
)


@injectable
class CustomersService:
    """
    Service layer for customer operations.
    
    Contains business logic and orchestrates repository calls.
    """
    
    def __init__(self, repository: CustomersRepository):
        self.repository = repository
    
    def create_customer(
        self,
        user_id: str,
        data: CustomerCreate,
    ) -> CustomerResponse:
        """
        Create a new customer profile.
        
        A customer profile is created when a user wants to start KYC.
        """
        # Check if customer already exists for this user
        existing = self.repository.find_by_user_id(user_id)
        if existing:
            return existing
        
        return self.repository.create(user_id, data)
    
    def get_customer(self, customer_id: str) -> CustomerResponse:
        """Get customer by ID."""
        customer = self.repository.find_by_id(customer_id)
        
        if not customer:
            raise CustomerNotFoundError(customer_id)
        
        return customer
    
    def get_customer_by_user(self, user_id: str) -> Optional[CustomerResponse]:
        """Get customer profile for a user."""
        return self.repository.find_by_user_id(user_id)
    
    def list_customers(
        self,
        page: int = 1,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> CustomerListResponse:
        """
        List customers with pagination.
        
        Admin-only endpoint.
        """
        skip = (page - 1) * limit
        customers, total = self.repository.find_all(skip, limit, status)
        
        return CustomerListResponse(
            customers=customers,
            total=total,
            page=page,
            limit=limit,
        )
    
    def update_customer(
        self,
        customer_id: str,
        data: CustomerUpdate,
    ) -> CustomerResponse:
        """Update customer information."""
        customer = self.repository.update(customer_id, data)
        
        if not customer:
            raise CustomerNotFoundError(customer_id)
        
        return customer
    
    def delete_customer(self, customer_id: str) -> bool:
        """Delete a customer profile."""
        if not self.repository.find_by_id(customer_id):
            raise CustomerNotFoundError(customer_id)
        
        return self.repository.delete(customer_id)
