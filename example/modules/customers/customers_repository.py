"""
Customers Repository - Data access layer for customers.

In production, this would use a real database.
For this demo, we use an in-memory dictionary.
"""

from typing import Optional, List
from datetime import datetime
import uuid

from tachyon_api import injectable

from .customers_dto import CustomerCreate, CustomerUpdate, CustomerResponse, AddressDTO


# Mock database
_customers_db: dict = {}


@injectable
class CustomersRepository:
    """
    Repository for customer data access.
    
    Methods follow the Repository Pattern:
    - create: Insert new record
    - find_by_id: Get single record
    - find_by_user_id: Get by foreign key
    - find_all: Get multiple records
    - update: Modify existing record
    - delete: Remove record
    """
    
    def create(self, user_id: str, data: CustomerCreate) -> CustomerResponse:
        """Create a new customer."""
        customer_id = f"cust_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        
        customer = {
            "customer_id": customer_id,
            "user_id": user_id,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "email": data.email,
            "phone": data.phone,
            "date_of_birth": data.date_of_birth,
            "address": data.address,
            "kyc_status": "pending",
            "created_at": now,
            "updated_at": now,
        }
        
        _customers_db[customer_id] = customer
        
        return self._to_response(customer)
    
    def find_by_id(self, customer_id: str) -> Optional[CustomerResponse]:
        """Find a customer by ID."""
        customer = _customers_db.get(customer_id)
        
        if not customer:
            return None
        
        return self._to_response(customer)
    
    def find_by_user_id(self, user_id: str) -> Optional[CustomerResponse]:
        """Find a customer by user ID."""
        for customer in _customers_db.values():
            if customer["user_id"] == user_id:
                return self._to_response(customer)
        return None
    
    def find_all(
        self,
        skip: int = 0,
        limit: int = 10,
        status: Optional[str] = None,
    ) -> tuple[List[CustomerResponse], int]:
        """
        Find all customers with pagination.
        
        Returns tuple of (customers, total_count).
        """
        customers = list(_customers_db.values())
        
        # Filter by status if provided
        if status:
            customers = [c for c in customers if c["kyc_status"] == status]
        
        total = len(customers)
        
        # Paginate
        customers = customers[skip:skip + limit]
        
        return [self._to_response(c) for c in customers], total
    
    def update(
        self,
        customer_id: str,
        data: CustomerUpdate,
    ) -> Optional[CustomerResponse]:
        """Update a customer."""
        customer = _customers_db.get(customer_id)
        
        if not customer:
            return None
        
        # Update fields if provided
        if data.first_name is not None:
            customer["first_name"] = data.first_name
        if data.last_name is not None:
            customer["last_name"] = data.last_name
        if data.phone is not None:
            customer["phone"] = data.phone
        if data.date_of_birth is not None:
            customer["date_of_birth"] = data.date_of_birth
        if data.address is not None:
            customer["address"] = data.address
        
        customer["updated_at"] = datetime.utcnow().isoformat()
        
        return self._to_response(customer)
    
    def update_kyc_status(
        self,
        customer_id: str,
        status: str,
    ) -> Optional[CustomerResponse]:
        """Update customer's KYC status."""
        customer = _customers_db.get(customer_id)
        
        if not customer:
            return None
        
        customer["kyc_status"] = status
        customer["updated_at"] = datetime.utcnow().isoformat()
        
        return self._to_response(customer)
    
    def delete(self, customer_id: str) -> bool:
        """Delete a customer."""
        if customer_id in _customers_db:
            del _customers_db[customer_id]
            return True
        return False
    
    def _to_response(self, customer: dict) -> CustomerResponse:
        """Convert database record to response DTO."""
        address = customer.get("address")
        if address and isinstance(address, dict):
            address = AddressDTO(**address)
        
        return CustomerResponse(
            customer_id=customer["customer_id"],
            user_id=customer["user_id"],
            first_name=customer["first_name"],
            last_name=customer["last_name"],
            email=customer["email"],
            phone=customer.get("phone"),
            date_of_birth=customer.get("date_of_birth"),
            address=address,
            kyc_status=customer.get("kyc_status", "pending"),
            created_at=customer.get("created_at", ""),
            updated_at=customer.get("updated_at", ""),
        )
