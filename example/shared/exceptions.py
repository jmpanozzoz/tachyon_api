"""
Custom exceptions for KYC Demo API.

These provide clear, descriptive errors for different failure scenarios.
"""

from tachyon_api import HTTPException


class KYCException(HTTPException):
    """Base exception for KYC-related errors."""
    
    def __init__(
        self,
        status_code: int = 400,
        detail: str = "KYC operation failed",
        error_code: str = "KYC_ERROR",
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code


class CustomerNotFoundError(KYCException):
    """Raised when a customer is not found."""
    
    def __init__(self, customer_id: str):
        super().__init__(
            status_code=404,
            detail=f"Customer '{customer_id}' not found",
            error_code="CUSTOMER_NOT_FOUND",
        )
        self.customer_id = customer_id


class VerificationNotFoundError(KYCException):
    """Raised when a verification is not found."""
    
    def __init__(self, verification_id: str):
        super().__init__(
            status_code=404,
            detail=f"Verification '{verification_id}' not found",
            error_code="VERIFICATION_NOT_FOUND",
        )
        self.verification_id = verification_id


class UnauthorizedError(KYCException):
    """Raised when authentication fails."""
    
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(
            status_code=401,
            detail=detail,
            error_code="UNAUTHORIZED",
        )
