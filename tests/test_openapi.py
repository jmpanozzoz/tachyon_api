import pytest
from httpx import AsyncClient, ASGITransport
from tachyon_api import Tachyon
from tachyon_api.params import Body, Path
from tachyon_api.models import Struct
from tachyon_api.openapi import (
    create_openapi_config,
    OpenAPIGenerator,
    Contact,
    License,
    Server,
)


class Item(Struct):
    """Test model for OpenAPI generation"""

    name: str
    price: float


@pytest.mark.asyncio
async def test_openapi_schema_generation():
    """
    Tests that a valid OpenAPI schema is generated and served at /openapi.json.

    It verifies that the schema correctly reflects the application's routes,
    parameters, and models defined in the test fixture.
    """
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/")
    def home():
        return {"message": "Tachyon is running!"}

    @app.get("/items/{item_id}")
    def get_item(item_id: int = Path()):
        return {"item_id_received": item_id, "type": "int"}

    @app.post("/items")
    def create_item(item: Item = Body()):
        """Create a new item"""
        return {
            "message": "Item created",
            "item_name": item.name,
            "item_price": item.price,
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()

    # --- Verification Section ---

    # 1. Verify basic OpenAPI structure
    assert schema["openapi"] == "3.0.0"
    assert schema["info"]["title"] == "Tachyon API"

    # 2. Verify a route with a Path Parameter is documented
    assert "/items/{item_id}" in schema["paths"]
    path_item = schema["paths"]["/items/{item_id}"]["get"]
    assert "summary" in path_item
    param = path_item["parameters"][0]
    assert param["name"] == "item_id"
    assert param["in"] == "path"
    assert param["required"] is True
    assert param["schema"]["type"] == "integer"

    # 3. Verify a route with a Body Parameter is documented
    post_item = schema["paths"]["/items"]["post"]
    request_body = post_item["requestBody"]
    assert (
        request_body["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/Item"
    )

    # 4. Verify that the model (Struct) is defined in components
    component_schema = schema["components"]["schemas"]["Item"]
    assert component_schema["type"] == "object"
    assert component_schema["properties"]["name"]["type"] == "string"
    assert component_schema["properties"]["price"]["type"] == "number"


def test_default_openapi_config():
    """Test that the default configuration works"""
    config = create_openapi_config()

    assert config.info.title == "Tachyon API"
    assert config.info.description == "A fast API built with Tachyon"
    assert config.info.version == "0.1.0"
    assert config.openapi_version == "3.0.0"
    assert config.docs_url == "/docs"
    assert config.redoc_url == "/redoc"
    assert config.openapi_url == "/openapi.json"


def test_custom_openapi_config():
    """Test for custom configuration similar to FastAPI"""
    contact = Contact(
        name="Development Team",
        url="https://example.com/contact",
        email="dev@example.com",
    )

    license = License(name="MIT", url="https://opensource.org/licenses/MIT")

    servers = [
        Server(url="https://api.example.com", description="Production server"),
        Server(url="https://staging-api.example.com", description="Staging server"),
    ]

    config = create_openapi_config(
        title="My Custom API",
        description="This is my custom API with Tachyon",
        version="1.2.3",
        contact=contact,
        license=license,
        servers=servers,
        docs_url="/documentation",
        redoc_url="/redoc-docs",
        swagger_ui_parameters={"deepLinking": True, "displayRequestDuration": True},
    )

    assert config.info.title == "My Custom API"
    assert config.info.description == "This is my custom API with Tachyon"
    assert config.info.version == "1.2.3"
    assert config.info.contact.name == "Development Team"
    assert config.info.license.name == "MIT"
    assert len(config.servers) == 2
    assert config.docs_url == "/documentation"
    assert config.swagger_ui_parameters["deepLinking"] is True


def test_openapi_generator():
    """Test that the OpenAPI generator works correctly"""
    config = create_openapi_config(title="Test API", description="Test API")

    generator = OpenAPIGenerator(config)
    schema = generator.get_openapi_schema()

    assert schema["openapi"] == "3.0.0"
    assert schema["info"]["title"] == "Test API"
    assert schema["info"]["description"] == "Test API"
    assert "paths" in schema
    assert "components" in schema


def test_swagger_ui_html_generation():
    """Test HTML generation for Swagger UI"""
    config = create_openapi_config(title="Test API")
    generator = OpenAPIGenerator(config)

    html = generator.get_swagger_ui_html("/openapi.json", "Test API")

    assert "<!DOCTYPE html>" in html
    assert "swagger-ui" in html
    assert "/openapi.json" in html
    assert "Test API" in html


def test_redoc_html_generation():
    """Test HTML generation for ReDoc"""
    config = create_openapi_config(title="Test API")
    generator = OpenAPIGenerator(config)

    html = generator.get_redoc_html("/openapi.json", "Test API")

    assert "<!DOCTYPE html>" in html
    assert "redoc" in html
    assert "/openapi.json" in html
    assert "Test API" in html


def test_add_path_to_schema():
    """Test adding routes to the OpenAPI schema"""
    generator = OpenAPIGenerator()

    operation_data = {
        "summary": "Get user",
        "description": "Gets information about a user",
        "responses": {
            "200": {
                "description": "User found",
                "content": {"application/json": {"schema": {"type": "object"}}},
            }
        },
    }

    generator.add_path("/users/{user_id}", "get", operation_data)
    schema = generator.get_openapi_schema()

    assert "/users/{user_id}" in schema["paths"]
    assert "get" in schema["paths"]["/users/{user_id}"]
    assert schema["paths"]["/users/{user_id}"]["get"]["summary"] == "Get user"


def test_contact_to_dict():
    """Test conversion of Contact to dictionary"""
    contact = Contact(
        name="John Doe", url="https://example.com", email="john@example.com"
    )

    result = contact.to_dict()

    assert result["name"] == "John Doe"
    assert result["url"] == "https://example.com"
    assert result["email"] == "john@example.com"


def test_license_to_dict():
    """Test conversion of License to dictionary"""
    license = License(name="Apache 2.0", url="https://apache.org/licenses/LICENSE-2.0")

    result = license.to_dict()

    assert result["name"] == "Apache 2.0"
    assert result["url"] == "https://apache.org/licenses/LICENSE-2.0"


def test_server_to_dict():
    """Test conversion of Server to dictionary"""
    server = Server(url="https://api.example.com", description="Main server")

    result = server.to_dict()

    assert result["url"] == "https://api.example.com"
    assert result["description"] == "Main server"


def test_scalar_html_generation():
    """Test HTML generation for Scalar API Reference"""
    config = create_openapi_config(title="Test API")
    generator = OpenAPIGenerator(config)

    html = generator.get_scalar_html("/openapi.json", "Test API")

    assert "<!DOCTYPE html>" in html
    assert 'id="api-reference"' in html
    assert 'data-url="/openapi.json"' in html
    assert "Test API" in html
    assert config.scalar_js_url in html
