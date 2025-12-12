"""
Documents Service - Document management business logic.
"""

from datetime import datetime
import uuid

from tachyon_api import injectable

from ...config import settings
from ...shared.exceptions import (
    DocumentNotFoundError,
    InvalidDocumentError,
    CustomerNotFoundError,
)
from ..customers.customers_repository import CustomersRepository
from .documents_dto import DocumentResponse, DocumentListResponse


# Mock document storage
_documents_db: dict = {}


@injectable
class DocumentsService:
    """
    Service for document operations.
    
    In production, this would:
    - Store files in S3/GCS/Azure Blob
    - Run OCR for data extraction
    - Perform liveness detection for selfies
    """
    
    def __init__(self, customers_repository: CustomersRepository):
        self.customers_repository = customers_repository
    
    async def upload_document(
        self,
        customer_id: str,
        document_type: str,
        filename: str,
        content_type: str,
        file_content: bytes,
    ) -> DocumentResponse:
        """
        Upload a document for KYC.
        
        Validates the document and stores it.
        """
        # Verify customer exists
        customer = self.customers_repository.find_by_id(customer_id)
        if not customer:
            raise CustomerNotFoundError(customer_id)
        
        # Validate content type
        if content_type not in settings.allowed_document_types:
            raise InvalidDocumentError(
                f"File type '{content_type}' not allowed. "
                f"Allowed types: {settings.allowed_document_types}"
            )
        
        # Validate file size
        size_bytes = len(file_content)
        max_size = settings.max_document_size_mb * 1024 * 1024
        
        if size_bytes > max_size:
            raise InvalidDocumentError(
                f"File size ({size_bytes} bytes) exceeds maximum "
                f"({settings.max_document_size_mb} MB)"
            )
        
        # Validate document type
        valid_types = [
            "passport",
            "drivers_license",
            "national_id",
            "selfie",
            "proof_of_address",
        ]
        if document_type not in valid_types:
            raise InvalidDocumentError(
                f"Invalid document type '{document_type}'. "
                f"Valid types: {valid_types}"
            )
        
        # Create document record
        document_id = f"doc_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        
        document = {
            "document_id": document_id,
            "customer_id": customer_id,
            "document_type": document_type,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "status": "uploaded",
            "uploaded_at": now,
            "verified_at": None,
            # In production, store file reference, not content
            "_content": file_content,
        }
        
        _documents_db[document_id] = document
        
        return self._to_response(document)
    
    def get_document(self, document_id: str) -> DocumentResponse:
        """Get document by ID."""
        document = _documents_db.get(document_id)
        
        if not document:
            raise DocumentNotFoundError(document_id)
        
        return self._to_response(document)
    
    def get_documents_for_customer(
        self,
        customer_id: str,
    ) -> DocumentListResponse:
        """Get all documents for a customer."""
        documents = [
            d for d in _documents_db.values()
            if d["customer_id"] == customer_id
        ]
        
        return DocumentListResponse(
            documents=[self._to_response(d) for d in documents],
            total=len(documents),
        )
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document."""
        if document_id not in _documents_db:
            raise DocumentNotFoundError(document_id)
        
        del _documents_db[document_id]
        return True
    
    def get_document_content(self, document_id: str) -> tuple[bytes, str, str]:
        """
        Get document content for download.
        
        Returns tuple of (content, content_type, filename).
        """
        document = _documents_db.get(document_id)
        
        if not document:
            raise DocumentNotFoundError(document_id)
        
        return (
            document["_content"],
            document["content_type"],
            document["filename"],
        )
    
    def _to_response(self, document: dict) -> DocumentResponse:
        """Convert database record to response DTO."""
        return DocumentResponse(
            document_id=document["document_id"],
            customer_id=document["customer_id"],
            document_type=document["document_type"],
            filename=document["filename"],
            content_type=document["content_type"],
            size_bytes=document["size_bytes"],
            status=document.get("status", "uploaded"),
            uploaded_at=document.get("uploaded_at", ""),
            verified_at=document.get("verified_at"),
        )
