import pytest
from tachyon_api import Tachyon
from tests.helpers import create_client
from tachyon_api.di import injectable, Depends
from tests.shared import MockUserService


@pytest.mark.asyncio
async def test_explicit_dependency_injection():
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/di_explicit/{user_id}")
    def get_user_explicitly(user_id: int, service: MockUserService = Depends()):
        return service.get_user_data(user_id)

    async with create_client(app) as client:
        response = await client.get("/di_explicit/123")

    assert response.status_code == 200
    assert response.json()["source"] == "mock_db"


@pytest.mark.asyncio
async def test_implicit_dependency_injection():
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/di_implicit/{user_id}")
    def get_user_implicitly(user_id: int, service: MockUserService):
        return service.get_user_data(user_id)

    async with create_client(app) as client:
        response = await client.get("/di_implicit/456")

    assert response.status_code == 200
    assert response.json()["id"] == 456
    assert response.json()["source"] == "mock_db"


@pytest.mark.asyncio
async def test_request_scoped_class_di_creates_new_instance_per_request():
    """v1.2.993 regression guard — exercises the compiler.pyx scope-check fix.

    Before the fix, `has_callable_deps` on the compiled CompiledEndpoint was
    True only for `Depends(callable)`, never for non-singleton class DI.
    Without `has_callable_deps == True` the orchestrator skips allocating
    `dependency_cache`, which silently makes request-scoped classes behave
    like singletons in compiled mode (while pure-Python users were fine).
    This test reaches into the resolver enough to fail loudly if that
    divergence is reintroduced.
    """
    from tachyon_api.di import injectable, SCOPE_REQUEST

    @injectable(scope=SCOPE_REQUEST)
    class RequestScopedCounter:
        construction_count = 0

        def __init__(self):
            RequestScopedCounter.construction_count += 1
            self.id = RequestScopedCounter.construction_count

    app = Tachyon()

    @app.get("/scoped")
    def hit(c: RequestScopedCounter):
        return {"id": c.id}

    async with create_client(app) as client:
        r1 = await client.get("/scoped")
        r2 = await client.get("/scoped")
        r3 = await client.get("/scoped")

    # Request-scoped MUST construct a fresh instance per request.  Singleton
    # would return the same id for all three.
    ids = {r1.json()["id"], r2.json()["id"], r3.json()["id"]}
    assert len(ids) == 3, (
        f"request-scoped DI behaved like singleton — ids={ids}. "
        "Likely the compiler.pyx scope check has regressed (see v1.2.993)."
    )


@pytest.mark.asyncio
async def test_request_scoped_class_di_shares_instance_within_request():
    """Parity guard — the KIND_DEP_CLASS branch must forward dependency_cache.

    Two parameters annotated with the same request-scoped class must receive
    the SAME instance within a single request, and fresh instances across
    requests.  If the parameter processor resolves class deps without the
    per-request cache, each parameter constructs its own instance and
    request scope silently degrades to transient.
    """
    from tachyon_api.di import SCOPE_REQUEST

    @injectable(scope=SCOPE_REQUEST)
    class RequestScopedSession:
        construction_count = 0

        def __init__(self):
            RequestScopedSession.construction_count += 1
            self.id = RequestScopedSession.construction_count

    app = Tachyon()

    @app.get("/scoped-pair")
    def hit(a: RequestScopedSession, b: RequestScopedSession):
        return {"a": a.id, "b": b.id}

    async with create_client(app) as client:
        r1 = await client.get("/scoped-pair")
        r2 = await client.get("/scoped-pair")

    body1, body2 = r1.json(), r2.json()
    assert body1["a"] == body1["b"], (
        f"request-scoped DI constructed two instances in one request — {body1}. "
        "Likely the parameter processor is not forwarding dependency_cache "
        "to resolve_dependency (parameters.pyx parity drift)."
    )
    assert body2["a"] == body2["b"]
    assert body1["a"] != body2["a"], "instances must not leak across requests"


def test_circular_dependency_raises_type_error():
    from tachyon_api import Tachyon
    from tachyon_api.di import injectable
    from tachyon_api.processing.dependencies import DependencyResolver

    @injectable
    class CycleB:
        pass

    @injectable
    class CycleA:
        def __init__(self, b: CycleB):
            self.b = b

    # Create the cycle: patch CycleB to depend on CycleA
    def _cycleB_init(self, a: CycleA):
        self.a = a

    CycleB.__init__ = _cycleB_init  # type: ignore[method-assign]

    try:
        app = Tachyon()
        resolver = DependencyResolver(app)
        import pytest
        with pytest.raises(TypeError, match="[Cc]ircular"):
            resolver.resolve_dependency(CycleA)
    finally:
        del CycleB.__init__  # type: ignore[attr-defined]


def test_resolve_non_injectable_class_no_args():
    from tachyon_api.processing.dependencies import DependencyResolver
    app = Tachyon()
    resolver = DependencyResolver(app)

    class Plain:
        pass

    result = resolver.resolve_dependency(Plain)
    assert isinstance(result, Plain)


def test_resolve_non_injectable_class_with_required_args_raises():
    from tachyon_api.processing.dependencies import DependencyResolver
    app = Tachyon()
    resolver = DependencyResolver(app)

    class RequiresArgs:
        def __init__(self, x):
            self.x = x

    with pytest.raises(TypeError, match="injectable"):
        resolver.resolve_dependency(RequiresArgs)


def test_dependency_unannotated_param_raises():
    """Cover the param.annotation is inspect.Parameter.empty branch."""
    from tachyon_api.processing.dependencies import DependencyResolver

    @injectable
    class BadService:
        def __init__(self, x):  # no annotation on x
            self.x = x

    app = Tachyon()
    resolver = DependencyResolver(app)
    with pytest.raises(TypeError, match="no type annotation"):
        resolver.resolve_dependency(BadService)
