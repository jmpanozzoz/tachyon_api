"""
Tests for Customers module.

Demonstrates dependency_overrides for mocking.
"""

from ..app import app
from ..modules.customers.customers_repository import CustomersRepository
from ..modules.customers.customers_dto import CustomerResponse, AddressDTO


class MockCustomersRepository:
    """Mock repository for testing."""

    def __init__(self):
        self._customers = {}

    def create(self, user_id, data):
        customer_id = "mock_customer_001"
        self._customers[customer_id] = {
            "customer_id": customer_id,
            "user_id": user_id,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "email": data.email,
            "phone": None,
            "date_of_birth": None,
            "address": None,
            "kyc_status": "pending",
            "created_at": "",
            "updated_at": "",
        }
        return self._to_response(self._customers[customer_id])

    def find_by_id(self, customer_id):
        if customer_id not in self._customers:
            return None
        return self._to_response(self._customers[customer_id])

    def find_by_user_id(self, user_id):
        for c in self._customers.values():
            if c["user_id"] == user_id:
                return self._to_response(c)
        return None

    def find_all(self, skip=0, limit=10, status=None):
        customers = list(self._customers.values())
        return [self._to_response(c) for c in customers[skip : skip + limit]], len(
            customers
        )

    def update(self, customer_id, data):
        if customer_id not in self._customers:
            return None
        c = self._customers[customer_id]
        if data.first_name:
            c["first_name"] = data.first_name
        return self._to_response(c)

    def update_kyc_status(self, customer_id, status):
        if customer_id in self._customers:
            self._customers[customer_id]["kyc_status"] = status

    def delete(self, customer_id):
        if customer_id in self._customers:
            del self._customers[customer_id]
            return True
        return False

    def _to_response(self, c):
        address = c.get("address")
        if address and isinstance(address, dict):
            address = AddressDTO(**address)
        return CustomerResponse(
            customer_id=c["customer_id"],
            user_id=c["user_id"],
            first_name=c["first_name"],
            last_name=c["last_name"],
            email=c["email"],
            phone=c.get("phone"),
            date_of_birth=c.get("date_of_birth"),
            address=address,
            kyc_status=c.get("kyc_status", "pending"),
            created_at=c.get("created_at", ""),
            updated_at=c.get("updated_at", ""),
        )


class TestCustomersEndpoints:
    """Tests for customer endpoints."""

    def test_create_customer(self, client, auth_headers):
        """Should create a new customer."""
        # Use mock repository
        mock_repo = MockCustomersRepository()
        app.dependency_overrides[CustomersRepository] = lambda: mock_repo

        response = client.post(
            "/customers/",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"

    def test_create_and_get_customer(self, client, auth_headers):
        """Should create and retrieve a customer."""
        mock_repo = MockCustomersRepository()
        app.dependency_overrides[CustomersRepository] = lambda: mock_repo

        # Create
        create_response = client.post(
            "/customers/",
            json={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@example.com",
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 200
        customer_id = create_response.json()["customer_id"]

        # Get
        get_response = client.get(
            f"/customers/{customer_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["customer_id"] == customer_id

    def test_get_customer_not_found(self, client, auth_headers):
        """Should return 404 for non-existent customer."""
        mock_repo = MockCustomersRepository()
        app.dependency_overrides[CustomersRepository] = lambda: mock_repo

        response = client.get("/customers/nonexistent", headers=auth_headers)

        assert response.status_code == 404
