import pytest
from httpx import AsyncClient, ASGITransport
from tachyon_api.openapi import (
    create_openapi_config,
    OpenAPIGenerator,
    Contact,
    License,
    Server,
)


@pytest.mark.asyncio
async def test_openapi_schema_generation(app):
    """
    Tests that a valid OpenAPI schema is generated and served at /openapi.json.

    It verifies that the schema correctly reflects the application's routes,
    parameters, and models defined in the test fixture.
    """
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
    """Test configuración personalizada similar a FastAPI"""
    contact = Contact(
        name="Equipo de Desarrollo",
        url="https://ejemplo.com/contacto",
        email="dev@ejemplo.com",
    )

    license = License(name="MIT", url="https://opensource.org/licenses/MIT")

    servers = [
        Server(url="https://api.ejemplo.com", description="Servidor de producción"),
        Server(
            url="https://staging-api.ejemplo.com", description="Servidor de staging"
        ),
    ]

    config = create_openapi_config(
        title="Mi API Personalizada",
        description="Esta es mi API personalizada con Tachyon",
        version="1.2.3",
        contact=contact,
        license=license,
        servers=servers,
        docs_url="/documentacion",
        redoc_url="/redoc-docs",
        swagger_ui_parameters={"deepLinking": True, "displayRequestDuration": True},
    )

    assert config.info.title == "Mi API Personalizada"
    assert config.info.description == "Esta es mi API personalizada con Tachyon"
    assert config.info.version == "1.2.3"
    assert config.info.contact.name == "Equipo de Desarrollo"
    assert config.info.license.name == "MIT"
    assert len(config.servers) == 2
    assert config.docs_url == "/documentacion"
    assert config.swagger_ui_parameters["deepLinking"] is True


def test_openapi_generator():
    """Test que el generador OpenAPI funcione correctamente"""
    config = create_openapi_config(title="Test API", description="API de prueba")

    generator = OpenAPIGenerator(config)
    schema = generator.get_openapi_schema()

    assert schema["openapi"] == "3.0.0"
    assert schema["info"]["title"] == "Test API"
    assert schema["info"]["description"] == "API de prueba"
    assert "paths" in schema
    assert "components" in schema


def test_swagger_ui_html_generation():
    """Test generación de HTML para Swagger UI"""
    config = create_openapi_config(title="Test API")
    generator = OpenAPIGenerator(config)

    html = generator.get_swagger_ui_html("/openapi.json", "Test API")

    assert "<!DOCTYPE html>" in html
    assert "swagger-ui" in html
    assert "/openapi.json" in html
    assert "Test API" in html


def test_redoc_html_generation():
    """Test generación de HTML para ReDoc"""
    config = create_openapi_config(title="Test API")
    generator = OpenAPIGenerator(config)

    html = generator.get_redoc_html("/openapi.json", "Test API")

    assert "<!DOCTYPE html>" in html
    assert "redoc" in html
    assert "/openapi.json" in html
    assert "Test API" in html


def test_add_path_to_schema():
    """Test añadir rutas al esquema OpenAPI"""
    generator = OpenAPIGenerator()

    operation_data = {
        "summary": "Obtener usuario",
        "description": "Obtiene información de un usuario",
        "responses": {
            "200": {
                "description": "Usuario encontrado",
                "content": {"application/json": {"schema": {"type": "object"}}},
            }
        },
    }

    generator.add_path("/users/{user_id}", "get", operation_data)
    schema = generator.get_openapi_schema()

    assert "/users/{user_id}" in schema["paths"]
    assert "get" in schema["paths"]["/users/{user_id}"]
    assert schema["paths"]["/users/{user_id}"]["get"]["summary"] == "Obtener usuario"


def test_contact_to_dict():
    """Test conversión de Contact a diccionario"""
    contact = Contact(
        name="Juan Pérez", url="https://ejemplo.com", email="juan@ejemplo.com"
    )

    result = contact.to_dict()

    assert result["name"] == "Juan Pérez"
    assert result["url"] == "https://ejemplo.com"
    assert result["email"] == "juan@ejemplo.com"


def test_license_to_dict():
    """Test conversión de License a diccionario"""
    license = License(name="Apache 2.0", url="https://apache.org/licenses/LICENSE-2.0")

    result = license.to_dict()

    assert result["name"] == "Apache 2.0"
    assert result["url"] == "https://apache.org/licenses/LICENSE-2.0"


def test_server_to_dict():
    """Test conversión de Server a diccionario"""
    server = Server(url="https://api.ejemplo.com", description="Servidor principal")

    result = server.to_dict()

    assert result["url"] == "https://api.ejemplo.com"
    assert result["description"] == "Servidor principal"


def test_scalar_html_generation():
    """Test generación de HTML para Scalar API Reference"""
    config = create_openapi_config(title="Test API")
    generator = OpenAPIGenerator(config)

    html = generator.get_scalar_html("/openapi.json", "Test API")

    assert "<!DOCTYPE html>" in html
    assert 'id="api-reference"' in html
    assert 'data-url="/openapi.json"' in html
    assert "Test API" in html
    assert config.scalar_js_url in html
