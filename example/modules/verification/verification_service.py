"""
Verification Service - KYC verification business logic.

This service:
- Orchestrates the verification process
- Runs background tasks for processing
- Sends WebSocket notifications
- Caches results
"""

import asyncio
import random
from typing import List

from tachyon_api import injectable, cache

from ...shared.exceptions import (
    VerificationNotFoundError,
    CustomerNotFoundError,
)
from ...shared.websocket_manager import manager as ws_manager
from ..customers.customers_repository import CustomersRepository
from .verification_repository import VerificationRepository
from .verification_dto import (
    VerificationResponse,
    VerificationSummary,
)


@injectable
class VerificationService:
    """
    Service for KYC verification operations.
    
    Demonstrates:
    - Background task processing
    - WebSocket notifications
    - Caching
    - Inter-service communication
    """
    
    def __init__(
        self,
        repository: VerificationRepository,
        customers_repository: CustomersRepository,
    ):
        self.repository = repository
        self.customers_repository = customers_repository
    
    def start_verification(
        self,
        customer_id: str,
        verification_type: str = "standard",
    ) -> VerificationResponse:
        """
        Start a new KYC verification.
        
        This creates the verification record and triggers
        background processing.
        """
        # Verify customer exists
        customer = self.customers_repository.find_by_id(customer_id)
        if not customer:
            raise CustomerNotFoundError(customer_id)
        
        # Check for existing in-progress verification
        existing = self.repository.find_latest_by_customer(customer_id)
        if existing and existing.status in ("pending", "processing"):
            return existing
        
        # Create new verification
        verification = self.repository.create(customer_id, verification_type)
        
        # Update customer status
        self.customers_repository.update_kyc_status(customer_id, "in_progress")
        
        return verification
    
    async def process_verification(self, verification_id: str) -> None:
        """
        Process verification checks (background task).
        
        This simulates calling external verification providers:
        - Identity verification
        - Address verification
        - Sanctions screening
        - PEP (Politically Exposed Persons) check
        
        In production, this would call real APIs like:
        - Jumio, Onfido for identity
        - LexisNexis for sanctions
        """
        verification = self.repository.find_by_id(verification_id)
        
        if not verification:
            return
        
        # Update status to processing
        self.repository.update_status(verification_id, "processing")
        
        # Notify via WebSocket
        await ws_manager.notify_verification_status(
            verification.customer_id,
            verification_id,
            "processing",
            {"message": "Verification started"},
        )
        
        # Process each check (simulated)
        total_score = 0
        all_passed = True
        
        for check in verification.checks:
            # Simulate API call delay
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Mock verification result (random for demo)
            passed = random.random() > 0.1  # 90% pass rate
            status = "passed" if passed else "failed"
            
            if not passed:
                all_passed = False
            
            # Update check
            self.repository.update_check(
                verification_id,
                check.check_type,
                status,
                f"Mock {check.check_type} check completed",
            )
            
            # Notify progress
            await ws_manager.notify_verification_status(
                verification.customer_id,
                verification_id,
                "processing",
                {
                    "check": check.check_type,
                    "result": status,
                },
            )
            
            # Add to risk score
            if passed:
                total_score += 20
        
        # Calculate final risk score (0-100, lower is better)
        risk_score = 100 - min(total_score, 100)
        
        # Determine final status
        final_status = "verified" if all_passed else "rejected"
        
        # Update verification
        self.repository.update_status(
            verification_id,
            final_status,
            risk_score,
        )
        
        # Update customer KYC status
        self.customers_repository.update_kyc_status(
            verification.customer_id,
            final_status,
        )
        
        # Final notification
        await ws_manager.notify_verification_status(
            verification.customer_id,
            verification_id,
            final_status,
            {
                "risk_score": risk_score,
                "message": f"Verification {final_status}",
            },
        )
    
    @cache(TTL=300)  # Cache for 5 minutes
    def get_verification(self, verification_id: str) -> VerificationResponse:
        """
        Get verification by ID.
        
        Results are cached for 5 minutes to reduce database load.
        """
        verification = self.repository.find_by_id(verification_id)
        
        if not verification:
            raise VerificationNotFoundError(verification_id)
        
        return verification
    
    def get_verifications_for_customer(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> List[VerificationResponse]:
        """Get all verifications for a customer."""
        return self.repository.find_by_customer(customer_id, limit)
    
    def get_verification_summary(
        self,
        verification_id: str,
    ) -> VerificationSummary:
        """Get a summary of verification status."""
        verification = self.get_verification(verification_id)
        
        passed = sum(1 for c in verification.checks if c.status == "passed")
        failed = sum(1 for c in verification.checks if c.status == "failed")
        pending = sum(1 for c in verification.checks if c.status == "pending")
        
        return VerificationSummary(
            verification_id=verification_id,
            status=verification.status,
            checks_passed=passed,
            checks_failed=failed,
            checks_pending=pending,
        )
