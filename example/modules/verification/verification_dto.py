"""
Verification DTOs - Data Transfer Objects for KYC verification.
"""

from typing import Optional, List
from tachyon_api import Struct


class VerificationCheck(Struct):
    """Individual verification check result."""
    
    check_type: str  # identity, address, sanctions, pep
    status: str  # pending, passed, failed
    details: Optional[str] = None
    checked_at: Optional[str] = None


class StartVerificationRequest(Struct):
    """Request to start a new verification."""
    
    customer_id: str
    verification_type: str = "standard"  # standard, enhanced


class VerificationResponse(Struct):
    """Verification status response."""
    
    verification_id: str
    customer_id: str
    status: str  # pending, processing, verified, rejected, expired
    verification_type: str
    checks: List[VerificationCheck] = []
    risk_score: Optional[int] = None  # 0-100
    started_at: str = ""
    completed_at: Optional[str] = None
    expires_at: Optional[str] = None


class VerificationListResponse(Struct):
    """List of verifications."""
    
    verifications: List[VerificationResponse]
    total: int


class VerificationSummary(Struct):
    """Summary of verification status."""
    
    verification_id: str
    status: str
    checks_passed: int
    checks_failed: int
    checks_pending: int
