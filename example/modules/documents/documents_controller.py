"""
Documents Controller - Document upload endpoints.

Endpoints:
- POST /documents/upload - Upload a document
- GET /documents/{id} - Get document info
- GET /documents/customer/{id} - Get customer's documents
- DELETE /documents/{id} - Delete a document
"""

from tachyon_api import Router, Depends, Form, File
from tachyon_api.files import UploadFile
from starlette.responses import Response

from ...shared.dependencies import get_current_user
from .documents_service import DocumentsService
from .documents_dto import (
    DocumentResponse,
    DocumentListResponse,
    UploadResponse,
)


router = Router(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    customer_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    service: DocumentsService = Depends(),
):
    """
    Upload a document for KYC verification.
    
    **Document types:**
    - `passport` - Passport photo page
    - `drivers_license` - Driver's license (front)
    - `national_id` - National ID card
    - `selfie` - Selfie for liveness check
    - `proof_of_address` - Utility bill, bank statement, etc.
    
    **Allowed file types:**
    - image/jpeg
    - image/png
    - application/pdf
    
    **Max file size:** 10 MB
    """
    # Read file content
    content = await file.read()
    
    # Upload document
    document = await service.upload_document(
        customer_id=customer_id,
        document_type=document_type,
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        file_content=content,
    )
    
    return UploadResponse(
        document_id=document.document_id,
        message=f"Document '{document.filename}' uploaded successfully",
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    user: dict = Depends(get_current_user),
    service: DocumentsService = Depends(),
):
    """
    Get document information by ID.
    
    Returns metadata about the document (not the file content).
    """
    return service.get_document(document_id)


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    user: dict = Depends(get_current_user),
    service: DocumentsService = Depends(),
):
    """
    Download a document.
    
    Returns the actual file content.
    """
    content, content_type, filename = service.get_document_content(document_id)
    
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/customer/{customer_id}", response_model=DocumentListResponse)
def get_customer_documents(
    customer_id: str,
    user: dict = Depends(get_current_user),
    service: DocumentsService = Depends(),
):
    """
    Get all documents for a customer.
    
    Returns list of documents with their metadata.
    """
    return service.get_documents_for_customer(customer_id)


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    user: dict = Depends(get_current_user),
    service: DocumentsService = Depends(),
):
    """
    Delete a document.
    
    Removes the document from storage.
    """
    service.delete_document(document_id)
    return {"deleted": True, "document_id": document_id}
