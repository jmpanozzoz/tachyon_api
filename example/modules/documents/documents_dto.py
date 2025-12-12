"""
Documents DTOs - Data Transfer Objects for document management.
"""

from typing import Optional, List
from tachyon_api import Struct


class DocumentResponse(Struct):
    """Document information response."""
    
    document_id: str
    customer_id: str
    document_type: str  # passport, drivers_license, national_id, selfie, proof_of_address
    filename: str
    content_type: str
    size_bytes: int
    status: str = "uploaded"  # uploaded, verified, rejected
    uploaded_at: str = ""
    verified_at: Optional[str] = None


class DocumentListResponse(Struct):
    """List of documents."""
    
    documents: List[DocumentResponse]
    total: int


class UploadResponse(Struct):
    """Response after successful upload."""
    
    document_id: str
    message: str = "Document uploaded successfully"
