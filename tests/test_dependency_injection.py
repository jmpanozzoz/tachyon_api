import pytest
from tachyon_api import Tachyon
from tests.helpers import create_client
from tachyon_api.di import injectable, Depends
from tests.shared import MockRepository, MockUserService


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
