from starlette.testclient import TestClient

from tachyon_api import Tachyon
from tachyon_api.models import Struct


class OutModel(Struct):
    id: int
    name: str


def test_response_model_success_and_openapi_schema():
    app = Tachyon()

    @app.get("/users/{user_id}", response_model=OutModel)
    def get_user(user_id: int):
        # Return as dict; should be validated and coerced to OutModel
        return {"id": user_id, "name": "Alice"}

    client = TestClient(app)

    resp = client.get("/users/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"id": 1, "name": "Alice"}

    # OpenAPI must include response schema reference
    schema = client.get("/openapi.json").json()
    op = schema["paths"]["/users/{user_id}"]["get"]
    r200 = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in r200
    assert r200["$ref"].startswith("#/components/schemas/")


def test_response_model_validation_error_returns_500():
    app = Tachyon()

    @app.get("/broken", response_model=OutModel)
    def broken():
        # Missing required field 'name'
        return {"id": 5}

    client = TestClient(app)
    resp = client.get("/broken")
    assert resp.status_code == 500
    assert resp.json()["detail"].lower().startswith("response validation error")


def test_response_object_bypasses_validation():
    from starlette.responses import JSONResponse

    app = Tachyon()

    @app.get("/raw", response_model=OutModel)
    def raw():
        return JSONResponse({"ok": True})

    client = TestClient(app)
    resp = client.get("/raw")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
