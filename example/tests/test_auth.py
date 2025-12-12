"""
Tests for Auth module.
"""



class TestAuthEndpoints:
    """Tests for authentication endpoints."""
    
    def test_login_success(self, client):
        """Should return token for valid credentials."""
        response = client.post(
            "/auth/login",
            json={"email": "demo@example.com", "password": "demo123"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self, client):
        """Should reject invalid credentials."""
        response = client.post(
            "/auth/login",
            json={"email": "demo@example.com", "password": "wrong"},
        )
        
        assert response.status_code == 401
    
    def test_register_new_user(self, client):
        """Should register a new user."""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "full_name": "New User",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
    
    def test_get_current_user(self, client, auth_headers):
        """Should return current user info with valid token."""
        response = client.get("/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
    
    def test_get_current_user_no_token(self, client):
        """Should reject request without token."""
        response = client.get("/auth/me")
        
        assert response.status_code == 401
