"""
Verification Controller - KYC verification endpoints.

Endpoints:
- POST /verification/start - Start new verification
- GET /verification/{id} - Get verification status
- GET /verification/{id}/summary - Get summary
- GET /verification/customer/{id} - Get customer's verifications
"""

from tachyon_api import Router, Depends, Body, Query
from tachyon_api.background import BackgroundTasks

from ...shared.dependencies import get_current_user
from .verification_service import VerificationService
from .verification_dto import (
    StartVerificationRequest,
    VerificationResponse,
    VerificationSummary,
)


router = Router(prefix="/verification", tags=["Verification"])


@router.post("/start", response_model=VerificationResponse)
async def start_verification(
    data: StartVerificationRequest = Body(...),
    background_tasks: BackgroundTasks = None,
    user: dict = Depends(get_current_user),
    service: VerificationService = Depends(),
):
    """
    Start a new KYC verification.
    
    This initiates the verification process which runs asynchronously.
    Connect to the WebSocket endpoint to receive real-time updates.
    
    **Verification types:**
    - `standard`: Identity, Address, Sanctions (3 checks)
    - `enhanced`: Standard + PEP, Adverse Media (5 checks)
    
    **Status flow:**
    1. `pending` - Just created
    2. `processing` - Checks running
    3. `verified` - All checks passed
    4. `rejected` - One or more checks failed
    
    **WebSocket:**
    Connect to `/ws/notifications/{customer_id}` to receive updates.
    """
    verification = service.start_verification(
        data.customer_id,
        data.verification_type,
    )
    
    # Schedule background processing
    if background_tasks:
        background_tasks.add_task(
            service.process_verification,
            verification.verification_id,
        )
    
    return verification


@router.get("/{verification_id}", response_model=VerificationResponse)
def get_verification(
    verification_id: str,
    user: dict = Depends(get_current_user),
    service: VerificationService = Depends(),
):
    """
    Get verification status by ID.
    
    Returns the current status and all check results.
    """
    return service.get_verification(verification_id)


@router.get("/{verification_id}/summary", response_model=VerificationSummary)
def get_verification_summary(
    verification_id: str,
    user: dict = Depends(get_current_user),
    service: VerificationService = Depends(),
):
    """
    Get a summary of verification status.
    
    Quick overview showing passed/failed/pending counts.
    """
    return service.get_verification_summary(verification_id)


@router.get("/customer/{customer_id}")
def get_customer_verifications(
    customer_id: str,
    limit: int = Query(10),
    user: dict = Depends(get_current_user),
    service: VerificationService = Depends(),
):
    """
    Get all verifications for a customer.
    
    Returns verifications sorted by date (newest first).
    """
    return service.get_verifications_for_customer(customer_id, limit)


@router.post("/{verification_id}/retry", response_model=VerificationResponse)
async def retry_verification(
    verification_id: str,
    background_tasks: BackgroundTasks = None,
    user: dict = Depends(get_current_user),
    service: VerificationService = Depends(),
):
    """
    Retry a failed or expired verification.
    
    Creates a new verification for the same customer.
    """
    # Get existing verification to find customer
    existing = service.get_verification(verification_id)
    
    # Start new verification
    verification = service.start_verification(
        existing.customer_id,
        existing.verification_type,
    )
    
    # Schedule processing
    if background_tasks:
        background_tasks.add_task(
            service.process_verification,
            verification.verification_id,
        )
    
    return verification
