"""Every customer operation has an explicit ownership or administrator check."""
from tachyon_api import Router, Depends, Body, Query
import msgspec
from starlette.responses import StreamingResponse
from ...shared.dependencies import require_admin
from ...shared.dependencies import get_current_user
from .customers_service import CustomersService
from .customers_dto import CustomerCreate, CustomerResponse

router = Router(prefix="/customers", tags=["Customers"])


@router.post("/", response_model=CustomerResponse)
async def create_customer(data: CustomerCreate = Body(...), user: dict = Depends(get_current_user),
                          service: CustomersService = Depends()):
    return await service.create_customer(user["user_id"], data)


@router.get("/me", response_model=CustomerResponse)
async def mine(user: dict = Depends(get_current_user), service: CustomersService = Depends()):
    return await service.mine(user)


@router.get("/recent", response_model=list[CustomerResponse])
async def recent(limit: int = Query(5), user: dict = Depends(get_current_user),
                 service: CustomersService = Depends()):
    return await service.recent(user, limit)


@router.get("/export")
async def export(user: dict = Depends(get_current_user), service: CustomersService = Depends()):
    require_admin(user)
    values = await service.recent(user, 100)
    # Materialize a bounded batch and release the read transaction before streaming.
    await service.repository.session.rollback()
    async def rows():
        for customer in values:
            yield msgspec.json.encode({"customer_id": customer.customer_id, "status": customer.kyc_status}) + b"\n"
    return StreamingResponse(rows(), media_type="application/x-ndjson")


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: str, user: dict = Depends(get_current_user),
                        service: CustomersService = Depends()):
    return await service.get_customer(customer_id, user)
