"""
Tests for Verification module.
"""

from ..app import app
from ..modules.customers.customers_repository import CustomersRepository
from ..modules.customers.customers_dto import CustomerResponse


class MockCustomersRepository:
    """Mock for customers repository."""

    def __init__(self):
        self._customers = {
            "valid_customer": {
                "customer_id": "valid_customer",
                "user_id": "test_user",
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
            }
        }

    def find_by_id(self, customer_id):
        if customer_id not in self._customers:
            return None
        c = self._customers[customer_id]
        return CustomerResponse(
            customer_id=c["customer_id"],
            user_id=c["user_id"],
            first_name=c["first_name"],
            last_name=c["last_name"],
            email=c["email"],
        )

    def update_kyc_status(self, customer_id, status):
        if customer_id in self._customers:
            self._customers[customer_id]["kyc_status"] = status


class TestVerificationEndpoints:
    """Tests for verification endpoints."""

    def test_start_verification(self, client, auth_headers):
        """Should start a new verification."""
        app.dependency_overrides[CustomersRepository] = MockCustomersRepository

        response = client.post(
            "/verification/start",
            json={
                "customer_id": "valid_customer",
                "verification_type": "standard",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "verification_id" in data
        assert data["status"] == "pending"
        assert data["verification_type"] == "standard"
        assert len(data["checks"]) == 3  # standard has 3 checks

    def test_start_enhanced_verification(self, client, auth_headers):
        """Should start enhanced verification with more checks."""
        app.dependency_overrides[CustomersRepository] = MockCustomersRepository

        response = client.post(
            "/verification/start",
            json={
                "customer_id": "valid_customer",
                "verification_type": "enhanced",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["checks"]) == 5  # enhanced has 5 checks

    def test_start_verification_invalid_customer(self, client, auth_headers):
        """Should reject verification for non-existent customer."""
        app.dependency_overrides[CustomersRepository] = MockCustomersRepository

        response = client.post(
            "/verification/start",
            json={
                "customer_id": "invalid_customer",
                "verification_type": "standard",
            },
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_get_verification(self, client, auth_headers):
        """Should get verification status."""
        app.dependency_overrides[CustomersRepository] = MockCustomersRepository

        # First create a verification
        create_response = client.post(
            "/verification/start",
            json={"customer_id": "valid_customer"},
            headers=auth_headers,
        )
        assert create_response.status_code == 200
        verification_id = create_response.json()["verification_id"]

        # Then get it
        response = client.get(
            f"/verification/{verification_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["verification_id"] == verification_id
