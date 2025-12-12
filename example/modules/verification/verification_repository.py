"""
Verification Repository - Data access for verifications.
"""

from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import msgspec

from tachyon_api import injectable

from ...config import settings
from .verification_dto import VerificationResponse, VerificationCheck


# Mock database
_verifications_db: dict = {}


@injectable
class VerificationRepository:
    """Repository for verification data access."""
    
    def create(
        self,
        customer_id: str,
        verification_type: str = "standard",
    ) -> VerificationResponse:
        """Create a new verification."""
        verification_id = f"ver_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=settings.verification_timeout_seconds)
        
        # Initial checks based on verification type
        checks = [
            VerificationCheck(check_type="identity", status="pending"),
            VerificationCheck(check_type="address", status="pending"),
            VerificationCheck(check_type="sanctions", status="pending"),
        ]
        
        if verification_type == "enhanced":
            checks.extend([
                VerificationCheck(check_type="pep", status="pending"),
                VerificationCheck(check_type="adverse_media", status="pending"),
            ])
        
        verification = {
            "verification_id": verification_id,
            "customer_id": customer_id,
            "status": "pending",
            "verification_type": verification_type,
            "checks": [msgspec.to_builtins(c) for c in checks],
            "risk_score": None,
            "started_at": now.isoformat(),
            "completed_at": None,
            "expires_at": expires_at.isoformat(),
        }
        
        _verifications_db[verification_id] = verification
        
        return self._to_response(verification)
    
    def find_by_id(self, verification_id: str) -> Optional[VerificationResponse]:
        """Find verification by ID."""
        verification = _verifications_db.get(verification_id)
        
        if not verification:
            return None
        
        return self._to_response(verification)
    
    def find_by_customer(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> List[VerificationResponse]:
        """Find all verifications for a customer."""
        verifications = [
            v for v in _verifications_db.values()
            if v["customer_id"] == customer_id
        ]
        
        # Sort by started_at descending
        verifications.sort(key=lambda x: x["started_at"], reverse=True)
        
        return [self._to_response(v) for v in verifications[:limit]]
    
    def find_latest_by_customer(
        self,
        customer_id: str,
    ) -> Optional[VerificationResponse]:
        """Find the latest verification for a customer."""
        verifications = self.find_by_customer(customer_id, limit=1)
        return verifications[0] if verifications else None
    
    def update_status(
        self,
        verification_id: str,
        status: str,
        risk_score: Optional[int] = None,
    ) -> Optional[VerificationResponse]:
        """Update verification status."""
        verification = _verifications_db.get(verification_id)
        
        if not verification:
            return None
        
        verification["status"] = status
        
        if risk_score is not None:
            verification["risk_score"] = risk_score
        
        if status in ("verified", "rejected"):
            verification["completed_at"] = datetime.utcnow().isoformat()
        
        return self._to_response(verification)
    
    def update_check(
        self,
        verification_id: str,
        check_type: str,
        status: str,
        details: Optional[str] = None,
    ) -> Optional[VerificationResponse]:
        """Update a specific check within a verification."""
        verification = _verifications_db.get(verification_id)
        
        if not verification:
            return None
        
        for check in verification["checks"]:
            if check["check_type"] == check_type:
                check["status"] = status
                check["details"] = details
                check["checked_at"] = datetime.utcnow().isoformat()
                break
        
        return self._to_response(verification)
    
    def _to_response(self, verification: dict) -> VerificationResponse:
        """Convert database record to response DTO."""
        checks = [
            VerificationCheck(**c) for c in verification.get("checks", [])
        ]
        
        return VerificationResponse(
            verification_id=verification["verification_id"],
            customer_id=verification["customer_id"],
            status=verification["status"],
            verification_type=verification["verification_type"],
            checks=checks,
            risk_score=verification.get("risk_score"),
            started_at=verification.get("started_at", ""),
            completed_at=verification.get("completed_at"),
            expires_at=verification.get("expires_at"),
        )
