# Cold path — registers the documentation routes (/docs, /redoc, /swagger, /openapi.json).
# Setup is lazy: triggered on the first incoming request via ASGIEntry.

from ..responses import HTMLResponse


class DocsRoutes:
    """Registers Tachyon's auto-generated documentation routes."""

    __slots__ = ("_app", "_setup_done")

    def __init__(self, app) -> None:
        self._app = app
        self._setup_done = False

    @property
    def setup_done(self) -> bool:
        return self._setup_done

    def setup(self) -> None:
        if self._setup_done:
            return
        self._setup_done = True

        app = self._app
        cfg = app.openapi_config
        gen = app.openapi_generator

        @app.get(cfg.openapi_url, include_in_schema=False)
        def get_openapi_schema():
            return gen.get_openapi_schema()

        @app.get(cfg.docs_url, include_in_schema=False)
        def get_scalar_docs():
            return HTMLResponse(gen.get_scalar_html(cfg.openapi_url, cfg.info.title))

        @app.get("/swagger", include_in_schema=False)
        def get_swagger_ui():
            return HTMLResponse(gen.get_swagger_ui_html(cfg.openapi_url, cfg.info.title))

        @app.get(cfg.redoc_url, include_in_schema=False)
        def get_redoc():
            return HTMLResponse(gen.get_redoc_html(cfg.openapi_url, cfg.info.title))
