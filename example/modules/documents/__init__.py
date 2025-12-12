"""
Documents Module - Document upload and management.

Features:
- Upload identity documents
- Upload selfie for liveness check
- List documents
- Download documents
"""

from .documents_controller import router

__all__ = ["router"]
