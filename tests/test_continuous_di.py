"""Registration and request contracts for dependency lifetimes and inputs."""

import pytest
from starlette.requests import Request
from starlette.websockets import WebSocket

from tachyon_api import Tachyon, Depends, Query, Header, Body, Cookie, Form, File, Path
from tachyon_api.di import injectable
from tachyon_api.processing.dependencies import DependencyResolver
from tests.helpers import create_client


@pytest.mark.parametrize("scope", ["session", "", None, 1])
def test_invalid_scope_rejected(scope):
    with pytest.raises(ValueError, match="Invalid dependency scope"):
        injectable(scope=scope)


@pytest.mark.parametrize("scope", ["request", "transient"])
@pytest.mark.parametrize("explicit", [False, True])
def test_singleton_rejects_shorter_lifetime_at_registration(scope, explicit):
    @injectable(scope=scope)
    class Context:
        pass

    @injectable
    class Service:
        def __init__(self, context: Context):
            self.context = context

    async def endpoint(service=Depends(Service) if explicit else Depends()):
        return None
    endpoint.__annotations__["service"] = Service
    app = Tachyon()
    with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
        app.get("/")(endpoint)
    assert not app._instances_cache


@pytest.mark.parametrize("connection_type", [Request, WebSocket])
def test_singleton_rejects_connection_at_registration(connection_type):
    @injectable
    class Service:
        def __init__(self, connection):
            self.connection = connection
    Service.__init__.__annotations__["connection"] = connection_type
    app = Tachyon()
    with pytest.raises(TypeError, match="cannot capture request parameter"):
        app.get("/")(lambda service=Depends(Service): None)
    assert not app._instances_cache


def test_singleton_rejects_indirect_callable_even_without_declared_inputs():
    def read_context():
        return "request-local globals or contextvars"

    @injectable
    class Child:
        def __init__(self, value=Depends(read_context)):
            self.value = value

    @injectable
    class Parent:
        def __init__(self, child: Child):
            self.child = child

    with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
        Tachyon().get("/")(lambda service=Depends(Parent): None)


@pytest.mark.parametrize("scope", ["request", "transient"])
@pytest.mark.asyncio
async def test_two_users_receive_their_own_nested_context(scope):
    @injectable(scope="request")
    class Context:
        def __init__(self, request: Request):
            self.user = request.headers["x-user"]

    @injectable(scope=scope)
    class Service:
        def __init__(self, context: Context):
            self.context = context

    app = Tachyon()

    @app.get("/")
    async def endpoint(service: Service, context: Context):
        return {"service": service.context.user, "request": context.user, "same": service.context is context}

    async with create_client(app) as client:
        for user in ("alice", "bob"):
            response = await client.get("/", headers={"x-user": user})
            assert response.json() == {"service": user, "request": user, "same": True}
    assert not app._instances_cache


@pytest.mark.asyncio
async def test_dependency_query_header_extraction_validation_and_request_cache():
    calls = []

    def credentials(identity: str = Header(..., alias="X-User"), count: int = Query(3), tags: list[int] = Query([])):
        calls.append(identity)
        return {"user": identity, "count": count, "tags": tags}

    app = Tachyon()

    @app.get("/")
    async def endpoint(first=Depends(credentials), second=Depends(credentials)):
        assert first is second
        return first

    async with create_client(app) as client:
        for user in ("alice", "bob"):
            response = await client.get("/?count=7&tags=1&tags=2", headers={"x-user": user})
            assert response.json() == {"user": user, "count": 7, "tags": [1, 2]}
        assert (await client.get("/", headers={"x-user": "default"})).json() == {"user": "default", "count": 3, "tags": []}
        assert (await client.get("/")).status_code == 422
        assert (await client.get("/?count=wrong", headers={"x-user": "alice"})).status_code == 422
    assert calls == ["alice", "bob", "default"]


@pytest.mark.parametrize("marker", [Body(), Cookie(), Form(), File(), Path()])
def test_unsupported_dependency_markers_rejected_at_registration(marker):
    def factory(value: str = marker):
        return value
    with pytest.raises(TypeError, match="not supported in dependency parameter"):
        Tachyon().get("/")(lambda value=Depends(factory): value)


@pytest.mark.parametrize("marker", [Header(), Query()])
def test_singleton_rejects_input_markers(marker):
    @injectable
    class Service:
        def __init__(self, value: str = marker):
            self.value = value
    with pytest.raises(TypeError, match="cannot capture request parameter"):
        Tachyon().get("/")(lambda service=Depends(Service): None)


@pytest.mark.asyncio
async def test_singleton_graph_rechecks_dynamic_overrides_before_capture():
    @injectable
    class Database:
        pass

    @injectable
    class Service:
        def __init__(self, db: Database):
            self.db = db

    app = Tachyon()
    resolver = DependencyResolver(app)

    def user_database(request: Request):
        return request.headers["x-user"]

    app.dependency_overrides[Database] = user_database
    with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
        await resolver.resolve_class_dependency(Service, {}, None)
    with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
        resolver.resolve_dependency(Service, {})
    assert not app._instances_cache
    app.dependency_overrides.clear()
    first = await resolver.resolve_class_dependency(Service, {}, None)
    assert isinstance(first.db, Database)
    assert resolver.resolve_dependency(Service) is first
    app.dependency_overrides[Database] = user_database
    with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
        await resolver.resolve_class_dependency(Service, {}, None)


@pytest.mark.asyncio
async def test_direct_override_factory_remains_request_local():
    @injectable
    class Service:
        pass

    def replacement(x_user: str = Header(...)):
        return x_user

    app = Tachyon()

    @app.get("/")
    async def endpoint(service: Service):
        return service

    app.dependency_overrides[Service] = replacement
    async with create_client(app) as client:
        for user in ("alice", "bob"):
            assert (await client.get("/", headers={"x-user": user})).json() == user
    assert not app._instances_cache


@pytest.mark.parametrize("scope", ["singleton", "request", "transient"])
def test_sync_resolution_is_safe_across_concurrent_threads(scope):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import time

    construction_calls = []
    start = Barrier(2)
    in_constructor = Barrier(2)

    @injectable(scope=scope)
    class Service:
        def __init__(self):
            construction_calls.append(1)
            if scope == "singleton":
                time.sleep(0.02)
            else:
                # Both request-local providers must build concurrently; shared
                # cycle state would reject the second construction incorrectly.
                in_constructor.wait(timeout=2)

    resolver = DependencyResolver(Tachyon())

    def resolve():
        start.wait(timeout=2)
        return resolver.resolve_dependency(Service, {})

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(resolve)
        second = pool.submit(resolve)
        instances = [first.result(timeout=3), second.result(timeout=3)]
    assert len(construction_calls) == (1 if scope == "singleton" else 2)
    assert (instances[0] is instances[1]) is (scope == "singleton")


def test_sync_resolution_stack_still_detects_recursive_user_construction():
    resolver = DependencyResolver(Tachyon())

    @injectable
    class Service:
        def __init__(self):
            resolver.resolve_dependency(Service)

    with pytest.raises(TypeError, match="Circular dependency"):
        resolver.resolve_dependency(Service)
    assert not resolver.app._instances_cache


@pytest.mark.asyncio
async def test_singleton_rejects_override_changed_during_async_construction():
    import asyncio
    from threading import Event

    entered, release = Event(), Event()
    factory_calls = []

    @injectable
    class Gate:
        def __init__(self):
            entered.set()
            assert release.wait(timeout=2)

    @injectable
    class Child:
        pass

    @injectable
    class Parent:
        def __init__(self, gate: Gate, child: Child):
            self.child = child

    def request_factory(request: Request):
        factory_calls.append(request.headers["x-user"])
        return request.headers["x-user"]

    app = Tachyon()
    resolver = DependencyResolver(app)
    request = Request({"type": "http", "headers": [(b"x-user", b"alice")]})
    task = asyncio.create_task(resolver.resolve_class_dependency(Parent, {}, request))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        app.dependency_overrides[Child] = request_factory
        release.set()
        with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
            await task
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert factory_calls == []
    assert Parent not in app._instances_cache
    assert Child not in app._instances_cache


def test_singleton_rejects_override_changed_during_sync_construction():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    entered, release = Event(), Event()
    factory_calls = []

    @injectable
    class Gate:
        def __init__(self):
            entered.set()
            assert release.wait(timeout=2)

    @injectable
    class Child:
        pass

    @injectable
    class Parent:
        def __init__(self, gate: Gate, child: Child):
            self.child = child

    def request_factory():
        factory_calls.append("alice")
        return "alice"

    app = Tachyon()
    resolver = DependencyResolver(app)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(resolver.resolve_dependency, Parent)
        try:
            assert entered.wait(timeout=2)
            app.dependency_overrides[Child] = request_factory
            release.set()
            with pytest.raises(TypeError, match="Singleton dependency cannot capture"):
                future.result(timeout=3)
        finally:
            release.set()
    assert factory_calls == []
    assert Parent not in app._instances_cache
    assert Child not in app._instances_cache


@pytest.mark.asyncio
async def test_changed_constant_override_does_not_reuse_previous_request_value():
    @injectable
    class Child:
        pass

    @injectable
    class Parent:
        def __init__(self, child: Child):
            self.child = child

    def request_factory(request: Request):
        return request.headers["x-user"]

    app = Tachyon()
    resolver = DependencyResolver(app)
    cache = {}
    request = Request({"type": "http", "headers": [(b"x-user", b"alice")]})
    app.dependency_overrides[Child] = request_factory
    assert await resolver.resolve_class_dependency(Child, cache, request) == "alice"
    configured_constant = object()
    app.dependency_overrides[Child] = configured_constant
    parent = await resolver.resolve_class_dependency(Parent, cache, request)
    assert parent.child is configured_constant


@pytest.mark.asyncio
async def test_root_override_added_while_waiting_for_lock_is_never_app_cached():
    import asyncio
    from threading import Event

    entered, release = Event(), Event()
    factory_calls = []

    @injectable
    class Service:
        def __init__(self):
            entered.set()
            assert release.wait(timeout=2)

    def request_factory(request: Request):
        factory_calls.append(request.headers["x-user"])
        return request.headers["x-user"]

    app = Tachyon()
    resolver = DependencyResolver(app)
    request = Request({"type": "http", "headers": [(b"x-user", b"alice")]})
    first = asyncio.create_task(resolver.resolve_class_dependency(Service, {}, request))
    second = None
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        second = asyncio.create_task(resolver.resolve_class_dependency(Service, {}, request))
        await asyncio.sleep(0)
        app.dependency_overrides[Service] = request_factory
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert all(isinstance(result, TypeError) for result in results)
    finally:
        release.set()
        await asyncio.gather(*(task for task in (first, second) if task is not None), return_exceptions=True)
    assert factory_calls == []
    assert Service not in app._instances_cache
    assert await resolver.resolve_class_dependency(Service, {}, request) == "alice"
    assert factory_calls == ["alice"]
    assert Service not in app._instances_cache
