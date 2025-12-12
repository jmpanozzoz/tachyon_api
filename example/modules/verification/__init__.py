"""
Verification Module - KYC verification process.

Features:
- Start verification
- Check verification status
- Process verification (background task)
- Real-time status updates (WebSocket)
- Caching of verification results
"""

from .verification_controller import router

__all__ = ["router"]
