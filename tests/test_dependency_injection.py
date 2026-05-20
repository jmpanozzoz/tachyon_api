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
