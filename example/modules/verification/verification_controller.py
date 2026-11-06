"""Durable verification operations, independent of HTTP background tasks."""
from tachyon_api import Router, Depends, Body, Header, File
from tachyon_api.files import UploadFile
import hashlib
from ...shared.exceptions import KYCException
from ...shared.dependencies import get_current_user
from .verification_service import VerificationService
from .verification_dto import StartVerificationRequest, VerificationResponse

router = Router(prefix="/verification", tags=["Verification"])


@router.post("/start", response_model=VerificationResponse)
async def start(data: StartVerificationRequest = Body(...),
                key: str = Header(..., alias="Idempotency-Key"),
                user: dict = Depends(get_current_user), service: VerificationService = Depends()):
    return await service.start(data, user, key)


@router.get("/{verification_id}", response_model=VerificationResponse)
async def get(verification_id: str, user: dict = Depends(get_current_user),
              service: VerificationService = Depends()):
    return await service.get(verification_id, user)


@router.post("/{verification_id}/document-check")
async def document_check(verification_id: str, document: UploadFile = File(...),
                          user: dict = Depends(get_current_user), service: VerificationService = Depends()):
    await service.get(verification_id, user)
    digest, size = hashlib.sha256(), 0
    while chunk := await document.read(64 * 1024):
        size += len(chunk)
        if size > 256 * 1024:
            raise KYCException(422, "Synthetic document exceeds 256 KiB", "DOCUMENT_TOO_LARGE")
        digest.update(chunk)
    return {"bytes": size, "sha256": digest.hexdigest(), "stored": False}
