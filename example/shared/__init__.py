"""
Shared utilities for KYC Demo API.
"""

from .exceptions import (
    KYCException,
    CustomerNotFoundError,
    VerificationNotFoundError,
    DocumentNotFoundError,
    InvalidDocumentError,
    VerificationAlreadyCompletedError,
)
from .dependencies import (
    get_current_user,
    get_current_customer,
    require_api_key,
)
from .websocket_manager import manager

__all__ = [
    # Exceptions
    "KYCException",
    "CustomerNotFoundError",
    "VerificationNotFoundError",
    "DocumentNotFoundError",
    "InvalidDocumentError",
    "VerificationAlreadyCompletedError",
    # Dependencies
    "get_current_user",
    "get_current_customer",
    "require_api_key",
    # WebSocket
    "manager",
]
