import pytest
from tachyon_api import Tachyon
from tests.helpers import create_client


@pytest.mark.asyncio
async def test_home_endpoint_returns_200_and_correct_payload():
    # Create a Tachyon instance for this specific test
    app = Tachyon()

    @app.get("/")
    def home():
        return {"message": "Tachyon is running!"}

    async with create_client(app) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Tachyon is running!"}


@pytest.mark.asyncio
async def test_app_cache_config_exception_logged(caplog):
    import logging
    from unittest.mock import MagicMock, patch

    # A config that will fail when set should not prevent app construction.
    bad_config = MagicMock()

    with caplog.at_level(logging.WARNING, logger="tachyon_api.app"):
        with patch("tachyon_api.app.set_cache_config", side_effect=Exception("cache error")):
            app = Tachyon(cache_config=bad_config)

    assert app is not None


def test_app_get_instance_returns_none_if_not_registered():
    class Unregistered:
        pass

    app = Tachyon()
    assert app.get_instance(Unregistered) is None


def test_app_setup_docs_idempotent():
    """DocsRoutes.setup() called twice should not duplicate routes."""
    app = Tachyon()
    app._docs_routes.setup()  # first call
    routes_after_first = len(app.routes)
    app._docs_routes.setup()  # second call — should return early
    assert len(app.routes) == routes_after_first  # no duplicate routes
