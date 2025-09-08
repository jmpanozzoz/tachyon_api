import pytest
from httpx import AsyncClient, ASGITransport
from starlette.responses import JSONResponse

from tachyon_api.schemas.responses import (
    success_response,
    error_response,
    not_found_response,
    conflict_response,
    validation_error_response,
)


class TestSimpleResponseHelpers:
    """Test suite for simple response helper functions"""

    def test_success_response_default(self):
        """Test success response with default message"""
        response = success_response({"user_id": 123})

        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

        # Check response content structure
        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is True
        assert data["message"] == "Success"
        assert data["data"] == {"user_id": 123}

    def test_success_response_custom_message(self):
        """Test success response with custom message and status"""
        response = success_response(
            {"user_id": 123}, message="User created successfully", status_code=201
        )

        assert response.status_code == 201

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is True
        assert data["message"] == "User created successfully"
        assert data["data"] == {"user_id": 123}

    def test_success_response_no_data(self):
        """Test success response without data"""
        response = success_response(message="Operation completed")

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is True
        assert data["message"] == "Operation completed"
        assert data["data"] is None

    def test_error_response_basic(self):
        """Test basic error response"""
        response = error_response("Something went wrong")

        assert response.status_code == 400

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is False
        assert data["error"] == "Something went wrong"
        assert "code" not in data

    def test_error_response_with_code(self):
        """Test error response with error code and custom status"""
        response = error_response(
            "Invalid input", status_code=422, code="VALIDATION_ERROR"
        )

        assert response.status_code == 422

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is False
        assert data["error"] == "Invalid input"
        assert data["code"] == "VALIDATION_ERROR"

    def test_not_found_response_default(self):
        """Test not found response with default message"""
        response = not_found_response()

        assert response.status_code == 404

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is False
        assert data["error"] == "Resource not found"
        assert data["code"] == "NOT_FOUND"

    def test_not_found_response_custom(self):
        """Test not found response with custom message"""
        response = not_found_response("User not found")

        assert response.status_code == 404

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is False
        assert data["error"] == "User not found"
        assert data["code"] == "NOT_FOUND"

    def test_conflict_response_default(self):
        """Test conflict response with default message"""
        response = conflict_response()

        assert response.status_code == 409

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is False
        assert data["error"] == "Resource conflict"
        assert data["code"] == "CONFLICT"

    def test_conflict_response_custom(self):
        """Test conflict response with custom message"""
        response = conflict_response("Item already exists")

        assert response.status_code == 409

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is False
        assert data["error"] == "Item already exists"
        assert data["code"] == "CONFLICT"

    def test_validation_error_response_basic(self):
        """Test validation error response without field errors"""
        response = validation_error_response()

        assert response.status_code == 422

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is False
        assert data["error"] == "Validation failed"
        assert data["code"] == "VALIDATION_ERROR"
        assert "errors" not in data

    def test_validation_error_response_with_errors(self):
        """Test validation error response with field errors"""
        field_errors = {
            "name": ["This field is required"],
            "email": ["Invalid email format", "Email already exists"],
        }

        response = validation_error_response(
            "Form validation failed", errors=field_errors
        )

        assert response.status_code == 422

        content = response.body.decode()
        import json

        data = json.loads(content)

        assert data["success"] is False
        assert data["error"] == "Form validation failed"
        assert data["code"] == "VALIDATION_ERROR"
        assert data["errors"] == field_errors

    def test_response_headers(self):
        """Test that responses accept custom headers"""
        response = JSONResponse(
            {"test": "data"}, headers={"X-Custom-Header": "custom-value"}
        )

        assert "X-Custom-Header" in response.headers
        assert response.headers["X-Custom-Header"] == "custom-value"


@pytest.mark.asyncio
class TestResponsesInEndpoints:
    """Test response helpers working in actual endpoints"""

    @pytest.fixture
    def app(self):
        """Create test app with response endpoints"""
        from tachyon_api import Tachyon
        from tachyon_api.schemas.responses import (
            success_response,
            error_response,
            not_found_response,
            conflict_response,
        )

        app = Tachyon()

        @app.get("/success")
        def success_endpoint():
            return success_response({"message": "All good"}, "Success response")

        @app.get("/error")
        def error_endpoint():
            return error_response("Something failed", status_code=400)

        @app.get("/not-found")
        def not_found_endpoint():
            return not_found_response("Item not found")

        @app.get("/conflict")
        def conflict_endpoint():
            return conflict_response("Duplicate entry")

        @app.get("/regular-json")
        def regular_json_endpoint():
            # Test that regular dict responses still work
            return {"regular": "response"}

        return app

    async def test_success_response_in_endpoint(self, app):
        """Test success response helper in actual endpoint"""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/success")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Success response"
        assert data["data"]["message"] == "All good"

    async def test_error_response_in_endpoint(self, app):
        """Test error response helper in actual endpoint"""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/error")

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Something failed"

    async def test_not_found_response_in_endpoint(self, app):
        """Test not found response helper in actual endpoint"""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/not-found")

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Item not found"
        assert data["code"] == "NOT_FOUND"

    async def test_conflict_response_in_endpoint(self, app):
        """Test conflict response helper in actual endpoint"""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/conflict")

        assert response.status_code == 409
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Duplicate entry"
        assert data["code"] == "CONFLICT"

    async def test_regular_json_still_works(self, app):
        """Test that regular JSON responses still work alongside helpers"""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/regular-json")

        assert response.status_code == 200
        data = response.json()
        assert data["regular"] == "response"


class TestStarletteCompatibility:
    """Test compatibility with Starlette responses"""

    def test_starlette_imports_available(self):
        """Test that Starlette response imports work"""
        from tachyon_api.schemas.responses import JSONResponse, HTMLResponse

        # Test that we can create responses
        json_resp = JSONResponse({"test": "data"})
        assert json_resp.status_code == 200

        html_resp = HTMLResponse("<h1>Test</h1>")
        assert html_resp.status_code == 200
        assert html_resp.media_type == "text/html"

    def test_response_helpers_return_starlette_responses(self):
        """Test that our helpers return actual Starlette JSONResponse objects"""
        from starlette.responses import JSONResponse

        response = success_response({"test": "data"})
        assert isinstance(response, JSONResponse)

        response = error_response("test error")
        assert isinstance(response, JSONResponse)

        response = not_found_response("not found")
        assert isinstance(response, JSONResponse)


class TestResponseConsistency:
    """Test response structure consistency"""

    def test_success_responses_have_consistent_structure(self):
        """Test that all success responses have the same structure"""
        response = success_response({"data": "test"})

        content = response.body.decode()
        import json

        data = json.loads(content)

        # All success responses should have these keys
        required_keys = ["success", "message", "data"]
        for key in required_keys:
            assert key in data

        assert data["success"] is True

    def test_error_responses_have_consistent_structure(self):
        """Test that all error responses have the same base structure"""
        responses = [
            error_response("test error"),
            not_found_response("not found"),
            conflict_response("conflict"),
            validation_error_response("validation failed"),
        ]

        for response in responses:
            content = response.body.decode()
            import json

            data = json.loads(content)

            # All error responses should have these keys
            required_keys = ["success", "error"]
            for key in required_keys:
                assert key in data

            assert data["success"] is False
