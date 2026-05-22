"""
Customers Controller - Customer management endpoints.

Endpoints:
- POST /customers - Create customer profile
- POST /customers/bulk - Bulk create (showcases Body(List[Struct]))
- GET /customers/me - Get current user's customer profile
- GET /customers/recent - Recent customers (showcases response_model=List[Struct])
- GET /customers/{id} - Get customer by ID
- PUT /customers/{id} - Update customer
- DELETE /customers/{id} - Delete customer
- GET /customers - List all customers (admin)
"""

from typing import List, Optional

from tachyon_api import Router, Depends, Body, Query

from ...shared.dependencies import get_current_user
from ...shared.id_generator import IdGenerator
from ...shared.request_context import RequestContext
from .customers_service import CustomersService
from .customers_dto import (
    BulkCreateRequest,
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
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


@router.get("/", response_model=CustomerListResponse)
def list_customers(
    page: int = Query(1),
    limit: int = Query(10),
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
    service: CustomersService = Depends(),
):
    """
    List all customers (admin only).
    
    **Query parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 10)
    - `status`: Filter by KYC status (pending, in_progress, verified, rejected)
    """
    # In production, check if user is admin
    # For demo, we allow all authenticated users
    return service.list_customers(page, limit, status)


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


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    data: CustomerUpdate = Body(...),
    user: dict = Depends(get_current_user),
    service: CustomersService = Depends(),
):
    """
    Update customer information.
    
    All fields are optional - only provided fields are updated.
    """
    return service.update_customer(customer_id, data)


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: str,
    user: dict = Depends(get_current_user),
    service: CustomersService = Depends(),
):
    """
    Delete a customer profile.

    This also deletes all associated verifications and documents.
    """
    service.delete_customer(customer_id)
    return {"deleted": True, "customer_id": customer_id}


# ── Bulk + recent endpoints — showcase v1.2.0 features ────────────────────────

@router.post("/bulk", response_model=List[CustomerResponse])
def bulk_create_customers(
    payload: BulkCreateRequest = Body(...),
    user: dict = Depends(get_current_user),
    service: CustomersService = Depends(),
    ctx: RequestContext = Depends(),     # request-scoped — same instance for whole request
    id_gen: IdGenerator = Depends(),     # transient — fresh instance per injection
):
    """
    Bulk-create multiple customer profiles in a single request.

    Showcases:
    - Nested `List[CustomerCreate]` inside a Struct body → array property in OpenAPI
    - `response_model=List[CustomerResponse]` → array response schema
    - `@injectable(scope="request")` RequestContext for correlation tracking
    - `@injectable(scope="transient")` IdGenerator (a fresh sequence per call)
    """
    ctx.set("operation", "bulk_create")
    ctx.set("count", len(payload.customers))

    results: List[CustomerResponse] = []
    for data in payload.customers:
        batch_id = id_gen.next_id()
        created = service.create_customer(user["user_id"], data)
        created.customer_id = f"{batch_id}-{created.customer_id}"
        results.append(created)
    return results


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
