from __future__ import annotations

import datetime
import threading

import msgspec
import pytest
from starlette.requests import Request
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from tachyon_api import Tachyon, Body, Query, Header, Cookie
from tachyon_api.di import Depends, injectable, SCOPE_REQUEST
from tachyon_api.models import Struct, encode_json, decode_json
from tachyon_api.processing.compiler import compile_endpoint
from tests.helpers import create_client


class AuditBase(Struct, rename="camel"):
    required_id: int


class AuditPayload(AuditBase, rename="camel", kw_only=True):
    required_nullable: int | None
    optional_name: str = "fallback"
    tags: list[int] = msgspec.field(default_factory=list)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["keyword", "gap", "positional"])
async def test_endpoint_argument_binding(kind):
    app = Tachyon()
    if kind == "keyword":
        async def endpoint(*, value: int = Query(...)):
            return {"value": value}
        expected = {"value": 3}
    elif kind == "gap":
        async def endpoint(ordinary=10, value: int = Query(...)):
            return {"ordinary": ordinary, "value": value}
        expected = {"ordinary": 10, "value": 3}
    else:
        async def endpoint(value: int = Query(...), /):
            return {"value": value}
        expected = {"value": 3}
    app.get("/binding")(endpoint)
    async with create_client(app) as client:
        response = await client.get("/binding?value=3")
    assert response.status_code == 200
    assert response.json() == expected


def test_route_compilation_is_not_cached_by_function():
    def endpoint(value: int):
        return value
    fixed = compile_endpoint(endpoint, "/fixed")
    dynamic = compile_endpoint(endpoint, "/{value}")
    assert fixed is not dynamic
    assert fixed.param_count == 0
    assert dynamic.param_count == 1


@pytest.mark.asyncio
async def test_postponed_body_request_and_optional_query():
    app = Tachyon()

    @app.post("/future")
    async def endpoint(request: Request, data: AuditPayload = Body(), values: list[int | None] = Query(...)):
        return {"method": request.method, "id": data.required_id, "values": values}

    async with create_client(app) as client:
        response = await client.post("/future?values=3&values=null", json={"requiredId": 4, "requiredNullable": None})
    assert response.status_code == 200
    assert response.json() == {"method": "POST", "id": 4, "values": [3, None]}


@pytest.mark.asyncio
@pytest.mark.parametrize("value,expected", [("true", True), ("0", False), ("OFF", False), ("banana", None)])
async def test_boolean_conversion_rejects_unknown_values(value, expected):
    app = Tachyon()

    @app.get("/boolean")
    async def endpoint(flag: bool | None = Query(...)):
        return {"flag": flag}

    async with create_client(app) as client:
        response = await client.get("/boolean", params={"flag": value})
    if expected is None:
        assert response.status_code == 422
    else:
        assert response.status_code == 200
        assert response.json() == {"flag": expected}


def test_json_options_and_generic_validation():
    value = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
    assert encode_json(value, option=0).endswith(b'+00:00"')
    assert encode_json(value).endswith(b'Z"')
    values = decode_json('[{"requiredId": 7, "requiredNullable": null}]', list[AuditPayload])
    assert isinstance(values[0], AuditPayload)
    with pytest.raises(msgspec.ValidationError):
        decode_json('[{"requiredId": "bad", "requiredNullable": null}]', list[AuditPayload])


@pytest.mark.asyncio
async def test_openapi_uses_wire_names_and_msgspec_required_defaults():
    app = Tachyon()

    @app.post("/schema", response_model=AuditPayload)
    async def endpoint(data: AuditPayload = Body(), x_token: str = Header("guest"), session: str = Cookie(..., alias="sid")):
        return data

    async with create_client(app) as client:
        schema = (await client.get("/openapi.json")).json()
    model = schema["components"]["schemas"]["AuditPayload"]
    assert set(model["required"]) == {"requiredId", "requiredNullable"}
    assert model["properties"]["requiredId"]["type"] == "integer"
    assert model["properties"]["requiredNullable"]["nullable"] is True
    assert model["properties"]["optionalName"]["default"] == "fallback"
    params = schema["paths"]["/schema"]["post"]["parameters"]
    assert [(p["name"], p["required"]) for p in params] == [("x-token", False), ("sid", True)]
    assert params[0]["schema"]["default"] == "guest"


@pytest.mark.asyncio
async def test_sync_dependencies_and_overrides_run_in_worker_and_cache():
    app = Tachyon()
    event_loop_thread = threading.get_ident()
    calls = []

    def dependency():
        calls.append(threading.get_ident())
        return len(calls)

    async def nested(first: int = Depends(dependency), second: int = Depends(dependency)):
        return first, second

    @app.get("/dependencies")
    async def endpoint(pair=Depends(nested)):
        return list(pair)

    async with create_client(app) as client:
        response = await client.get("/dependencies")
        assert response.json() == [1, 1]
        assert len(calls) == 1 and calls[0] != event_loop_thread
        calls.clear()
        app.dependency_overrides[dependency] = dependency
        response = await client.get("/dependencies")
    assert response.json() == [1, 1]
    assert len(calls) == 1 and calls[0] != event_loop_thread


@pytest.mark.asyncio
async def test_class_constructor_preserves_defaults_and_resolves_callable_dependencies():
    app = Tachyon()
    event_loop_thread = threading.get_ident()

    async def provide():
        return "injected"

    @injectable(scope=SCOPE_REQUEST)
    class Service:
        def __init__(self, count: int = 9, source=Depends(provide)):
            self.count = count
            self.source = source
            self.thread = threading.get_ident()

    @app.get("/class")
    async def endpoint(first: Service, second: Service):
        return {"same": first is second, "count": first.count, "source": first.source, "worker": first.thread != event_loop_thread}

    async with create_client(app) as client:
        response = await client.get("/class")
    assert response.status_code == 200
    assert response.json() == {"same": True, "count": 9, "source": "injected", "worker": True}


@pytest.mark.asyncio
async def test_async_callable_object_and_sync_returning_awaitable():
    app = Tachyon()

    class AsyncFactory:
        async def __call__(self):
            return 8

    def returning_awaitable():
        async def result():
            return 13
        return result()

    @app.get("/awaitable")
    async def endpoint(a=Depends(AsyncFactory()), b=Depends(returning_awaitable)):
        return [a, b]

    async with create_client(app) as client:
        response = await client.get("/awaitable")
    assert response.status_code == 200
    assert response.json() == [8, 13]


def test_websocket_dependencies_bind_resolver_and_share_request_scope():
    app = Tachyon()

    @injectable(scope=SCOPE_REQUEST)
    class Session:
        pass

    async def token(socket: WebSocket):
        return socket.query_params["token"]

    @app.websocket("/ws/{room}")
    async def endpoint(websocket: WebSocket, room: int, first: Session, second: Session, auth=Depends(token)):
        await websocket.accept()
        await websocket.send_json({"room": room, "same": first is second, "token": auth})
        await websocket.close()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/7?token=ok") as ws:
            assert ws.receive_json() == {"room": 7, "same": True, "token": "ok"}


def test_unresolved_annotation_fails_at_registration():
    app = Tachyon()

    async def endpoint(value: MissingAuditType = Query(...)):  # noqa: F821 — intentional unresolved annotation
        return value

    with pytest.raises(NameError, match="MissingAuditType"):
        app.get("/invalid")(endpoint)


def test_generator_dependency_registers_for_http():
    app = Tachyon()

    def dependency():
        yield "resource"

    @app.get("/generator")
    async def endpoint(value=Depends(dependency)):
        return value

    with TestClient(app) as client:
        assert client.get("/generator").json() == "resource"


@pytest.mark.asyncio
async def test_class_override_can_be_added_and_removed_after_singleton_warmup():
    app = Tachyon()

    @injectable
    class Service:
        value = "real"

    class Override:
        value = "override"

    @app.get("/override")
    async def endpoint(first: Service, second: Service):
        return {"value": first.value, "same": first is second}

    async with create_client(app) as client:
        assert (await client.get("/override")).json() == {"value": "real", "same": True}
        app.dependency_overrides[Service] = Override
        assert (await client.get("/override")).json() == {"value": "override", "same": True}
        app.dependency_overrides.clear()
        assert (await client.get("/override")).json() == {"value": "real", "same": True}


@pytest.mark.asyncio
async def test_singleton_constructor_is_not_duplicated_by_concurrent_requests():
    import asyncio
    app = Tachyon()
    calls = []

    @injectable
    class Provider:
        def __init__(self):
            import time
            calls.append(1)
            # Construction runs in a worker; keep it in flight while the other
            # request reaches the same singleton lock.
            time.sleep(0.01)
            self.value = 3

    @injectable
    class Service:
        def __init__(self, provider: Provider):
            self.value = provider.value

    @app.get("/singleton")
    async def endpoint(service: Service):
        return service.value

    async with create_client(app) as client:
        responses = await asyncio.gather(client.get("/singleton"), client.get("/singleton"))
    assert [r.json() for r in responses] == [3, 3]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_router_openapi_responses_merge_with_include_and_route_overrides():
    from tachyon_api.router import Router
    app = Tachyon()
    router = Router(prefix="/api", responses={401: {"description": "Unauthorized"}, 409: {"description": "Router conflict"}})

    @router.get("/responses", responses={403: {"description": "Route forbidden"}})
    async def endpoint():
        return {"ok": True}

    app.include_router(router, responses={403: {"description": "Include forbidden"}, 409: {"description": "Include conflict"}})
    async with create_client(app) as client:
        schema = (await client.get("/openapi.json")).json()
    responses = schema["paths"]["/api/responses"]["get"]["responses"]
    assert responses["401"] == {"description": "Unauthorized"}
    assert responses["403"] == {"description": "Route forbidden"}
    assert responses["409"] == {"description": "Include conflict"}
    assert "200" in responses


@pytest.mark.parametrize("responses", [[], {200: []}, {999: {"description": "Invalid"}}])
def test_invalid_openapi_response_configuration_fails_registration(responses):
    app = Tachyon()
    with pytest.raises((TypeError, ValueError), match="[Rr]esponse"):
        @app.get("/bad-responses", responses=responses)
        async def endpoint():
            return "ok"


@pytest.mark.asyncio
async def test_partial_dependency_retains_resolved_annotations():
    from functools import partial
    app = Tachyon()

    async def factory(prefix: str, request: Request):
        return prefix + request.url.path

    @app.get("/partial")
    async def endpoint(value=Depends(partial(factory, "request:"))):
        return value

    async with create_client(app) as client:
        response = await client.get("/partial")
    assert response.status_code == 200
    assert response.json() == "request:/partial"


def test_conflicting_openapi_component_names_fail_registration_without_overwrite():
    first = msgspec.defstruct("Payload", [("a", int)], module="module_a")
    second = msgspec.defstruct("Payload", [("b", str)], module="module_b")
    app = Tachyon()

    @app.get("/first", response_model=first)
    async def endpoint_a():
        return {"a": 1}

    with pytest.raises(ValueError, match="Conflicting OpenAPI component schema 'Payload'"):
        @app.get("/second", response_model=second)
        async def endpoint_b():
            return {"b": "two"}

    schema = app.openapi_generator.get_openapi_schema()
    assert schema["components"]["schemas"]["Payload"]["properties"] == {"a": {"type": "integer"}}
    assert "/second" not in schema["paths"]


def test_identical_openapi_component_names_with_identical_schemas_are_reusable():
    first = msgspec.defstruct("Payload", [("a", int)], module="module_a")
    second = msgspec.defstruct("Payload", [("a", int)], module="module_b")
    app = Tachyon()

    @app.get("/first", response_model=first)
    async def endpoint_a():
        return {"a": 1}

    @app.get("/second", response_model=second)
    async def endpoint_b():
        return {"a": 2}

    schema = app.openapi_generator.get_openapi_schema()
    assert schema["paths"]["/first"]["get"]["responses"]["200"] == schema["paths"]["/second"]["get"]["responses"]["200"]


@pytest.mark.asyncio
async def test_wrapped_dependency_uses_original_resolved_annotations():
    from functools import wraps
    app = Tachyon()

    async def factory(request: Request):
        return request.url.path

    @wraps(factory)
    def wrapped(*args, **kwargs):
        return factory(*args, **kwargs)

    @app.get("/wrapped")
    async def endpoint(value=Depends(wrapped)):
        return value

    async with create_client(app) as client:
        response = await client.get("/wrapped")
    assert response.status_code == 200
    assert response.json() == "/wrapped"


@pytest.mark.asyncio
async def test_openapi_schema_keywords_remain_valid_property_names_and_default_data():
    model = msgspec.defstruct(
        "SchemaKeywordFields",
        [("const", str), ("enum", int), ("anyOf", str),
         ("data", dict[str, str], msgspec.field(default_factory=lambda: {"const": "literal", "anyOf": "value", "exclusiveMinimum": "data"}))],
    )
    app = Tachyon()

    @app.get("/keyword-fields", response_model=model)
    async def endpoint():
        return {"const": "value", "enum": 2, "anyOf": "value"}

    async with create_client(app) as client:
        schema = (await client.get("/openapi.json")).json()
    properties = schema["components"]["schemas"]["SchemaKeywordFields"]["properties"]
    assert properties["const"] == {"type": "string"}
    assert properties["enum"] == {"type": "integer"}
    assert properties["anyOf"] == {"type": "string"}
    # msgspec omits factory-generated defaults; assert arbitrary JSON schema
    # defaults/examples directly to cover the adapter independently of that.
    from tachyon_api.openapi._struct_schemas import _openapi_schema
    data = {"const": "literal", "anyOf": "value", "exclusiveMinimum": 3}
    adapted = _openapi_schema({"type": "object", "default": data, "example": data, "examples": [data]})
    assert adapted["default"] == data
    assert adapted["example"] == data
    assert "examples" not in adapted


@pytest.mark.asyncio
async def test_openapi_30_numeric_exclusive_bounds_are_boolean_with_separate_limits():
    from typing import Annotated
    bounded = Annotated[float, msgspec.Meta(gt=0, lt=10)]
    model = msgspec.defstruct("ExclusiveBounds", [("value", bounded)])
    app = Tachyon()

    @app.get("/exclusive-bounds", response_model=model)
    async def endpoint():
        return {"value": 2.5}

    async with create_client(app) as client:
        schema = (await client.get("/openapi.json")).json()
    value = schema["components"]["schemas"]["ExclusiveBounds"]["properties"]["value"]
    assert value == {"type": "number", "minimum": 0, "exclusiveMinimum": True, "maximum": 10, "exclusiveMaximum": True}


@pytest.mark.parametrize("explicit", [False, True])
def test_class_constructor_generator_dependency_rejected_at_registration(explicit):
    def resource():
        yield "resource"

    @injectable
    class Service:
        def __init__(self, value=Depends(resource)):
            self.value = value

    app = Tachyon()
    if explicit:
        async def endpoint(value: Service = Depends()):
            return value
    else:
        async def endpoint(value: Service):
            return value
    with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
        app.get("/generator-class")(endpoint)


@pytest.mark.parametrize("explicit", [False, True])
def test_circular_class_dependency_rejected_at_registration(explicit):
    @injectable
    class First:
        def __init__(self, other: Second):
            self.other = other

    @injectable
    class Second:
        def __init__(self, other: First):
            self.other = other

    app = Tachyon()
    if explicit:
        async def endpoint(value: First = Depends()):
            return value
    else:
        async def endpoint(value: First):
            return value
    with pytest.raises(TypeError, match="Circular dependency"):
        app.get("/circular-class")(endpoint)


@pytest.mark.asyncio
async def test_openapi_30_converts_bytes_and_examples_without_mutating_example_payload():
    from typing import Annotated
    example = {"const": "payload", "anyOf": "data"}
    model = msgspec.defstruct("BytesAndExamples", [
        ("binary", bytes),
        ("metadata", Annotated[dict[str, str], msgspec.Meta(examples=[example, {"second": "example"}])]),
    ])
    app = Tachyon()

    @app.get("/bytes-examples", response_model=model)
    async def endpoint():
        return {"binary": b"bytes", "metadata": example}

    async with create_client(app) as client:
        schema = (await client.get("/openapi.json")).json()
    properties = schema["components"]["schemas"]["BytesAndExamples"]["properties"]
    assert properties["binary"] == {"type": "string", "format": "byte"}
    assert properties["metadata"]["example"] == example
    assert "examples" not in properties["metadata"]


@pytest.mark.parametrize("location", ["response", "body"])
@pytest.mark.parametrize("kind", ["tuple", "property_names"])
def test_unrepresentable_openapi_30_types_fail_at_registration(location, kind):
    from typing import Annotated
    model = tuple[int, str] if kind == "tuple" else dict[Annotated[str, msgspec.Meta(pattern="^x")], int]
    app = Tachyon()
    if location == "response":
        async def endpoint():
            return None
        options = {"response_model": model}
    else:
        async def endpoint(value=Body()):
            return value
        endpoint.__annotations__["value"] = model
        options = {}
    with pytest.raises(TypeError, match="OpenAPI 3.0 cannot represent"):
        app.post("/unsupported-schema", **options)(endpoint)
    assert "/unsupported-schema" not in app.openapi_generator.get_openapi_schema()["paths"]


def test_unrepresentable_schema_can_be_excluded_from_documentation():
    app = Tachyon()

    @app.get("/undocumented-tuple", response_model=tuple[int, str], include_in_schema=False)
    async def endpoint():
        return 1, "two"

    assert "/undocumented-tuple" not in app.openapi_generator.get_openapi_schema()["paths"]


def test_unsupported_openapi_version_is_rejected_explicitly():
    from tachyon_api.openapi import OpenAPIConfig
    with pytest.raises(ValueError, match="Only OpenAPI 3.0.x"):
        OpenAPIConfig(openapi_version="3.1.0")


@pytest.mark.asyncio
async def test_parameter_descriptions_omit_none():
    app = Tachyon()

    @app.get("/descriptions/{item_id}")
    async def endpoint(item_id: int, value: str = Query(...), token: str = Header(...)):
        return item_id

    async with create_client(app) as client:
        schema = (await client.get("/openapi.json")).json()
    parameters = schema["paths"]["/descriptions/{item_id}"]["get"]["parameters"]
    assert all(parameter.get("description", "") is not None for parameter in parameters)


def test_resolved_signatures_preserve_declared_types_with_none_defaults():
    from tachyon_api.background import BackgroundTasks
    from tachyon_api.processing.dependencies._sig_cache import get_signature

    def endpoint(request: Request = None, background: BackgroundTasks = None, optional: Request | None = None):
        return None

    signature = get_signature(endpoint)
    assert signature.parameters["request"].annotation is Request
    assert signature.parameters["background"].annotation is BackgroundTasks
    assert signature.parameters["optional"].annotation == Request | None
