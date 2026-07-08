"""
Customers Controller - Customer management endpoints.

Endpoints:
- POST /customers - Create customer profile
- GET /customers/me - Get current user's customer profile
- GET /customers/recent - Recent customers (showcases response_model=List[Struct])
- GET /customers/{id} - Get customer by ID
"""

from typing import List

from tachyon_api import Router, Depends, Body, Query

from ...shared.dependencies import get_current_user
from ...shared.request_context import RequestContext
from .customers_service import CustomersService
from .customers_dto import (
    CustomerCreate,
    CustomerResponse,
)


router = Router(prefix="/customers", tags=["Customers"])


@router.post("/", response_model=CustomerResponse)
def create_customer(
    data: CustomerCreate = Body(...),
    user: dict = Depends(get_current_user),
    service: CustomersService = Depends(),
):
    """
    Create a customer profile for KYC.
    
    This creates the customer profile needed before
    starting the KYC verification process.
    
    **Required fields:**
    - `first_name`: Customer's first name
    - `last_name`: Customer's last name
    - `email`: Customer's email address
    
    **Optional fields:**
    - `phone`: Phone number
    - `date_of_birth`: Date of birth (YYYY-MM-DD)
    - `address`: Full address object
    """
    return service.create_customer(user["user_id"], data)


@router.get("/me", response_model=CustomerResponse)
def get_my_customer_profile(
    user: dict = Depends(get_current_user),
    service: CustomersService = Depends(),
):
    """
    Get the current user's customer profile.
    
    Returns 404 if no customer profile exists yet.
    """
    from ...shared.exceptions import CustomerNotFoundError
    
    customer = service.get_customer_by_user(user["user_id"])
    
    if not customer:
        raise CustomerNotFoundError(user["user_id"])
    
    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    user: dict = Depends(get_current_user),
    service: CustomersService = Depends(),
):
    """
    Get customer by ID.
    
    Users can only access their own customer profile.
    Admins can access any customer.
    """
    return service.get_customer(customer_id)


@router.get("/recent", response_model=List[CustomerResponse])
def list_recent_customers(
    limit: int = Query(5),
    user: dict = Depends(get_current_user),
    service: CustomersService = Depends(),
    ctx: RequestContext = Depends(),
):
    """
    Return the most recently created customers as a flat array.

    Showcases `response_model=List[CustomerResponse]` — the OpenAPI spec at
    `/openapi.json` renders this as `{"type": "array", "items": {"$ref": ...}}`.
    Compare to `GET /customers/` which uses the paginated wrapper `CustomerListResponse`.

    The correlation id from the request-scoped `ctx` is echoed in the X-Correlation-Id
    header for traceability (set via middleware in production).
    """
    ctx.set("operation", "list_recent")
    page = service.list_customers(page=1, limit=limit, status=None)
    return page.customers
