"""
Shared utilities for KYC Demo API.
"""

from .exceptions import (
    KYCException,
    CustomerNotFoundError,
    VerificationNotFoundError,
)
from .dependencies import get_current_user
from .websocket_manager import manager

__all__ = [
    # Exceptions
    "KYCException",
    "CustomerNotFoundError",
    "VerificationNotFoundError",
    # Dependencies
    "get_current_user",
    # WebSocket
    "manager",
]
