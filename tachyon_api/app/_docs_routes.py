# Cold path — registers the documentation routes (/docs, /redoc, /swagger, /openapi.json).
# Setup is validated and prepared before publishing any documentation routes.

from starlette.requests import Request

from ..responses import HTMLResponse


class DocsRoutes:
    """Registers Tachyon's auto-generated documentation routes."""

    __slots__ = ("_app", "_setup_done", "_paths")

    def __init__(self, app) -> None:
        self._app = app
        self._setup_done = False
        self._paths = frozenset()

    @staticmethod
    def _key(path):
        return "/" + "/".join(part for part in path.split("/") if part)

    def check_user_route(self, path, method):
        if method.upper() == "GET" and self._key(path) in self._paths:
            raise ValueError(f"GET {path!r} conflicts with a documentation route; configure a different docs URL")

    @property
    def setup_done(self) -> bool:
        return self._setup_done

    def setup(self) -> None:
        if self._setup_done:
            return
        app = self._app
        cfg = app.openapi_config
        gen = app.openapi_generator
        if cfg is not gen.config:
            raise ValueError("Pass openapi_config to Tachyon() or edit its fields before serving; do not replace it")
        openapi_url = cfg.openapi_url
        if not isinstance(openapi_url, str):
            raise ValueError("The schema URL must be a string")
        remote_schema = openapi_url.lower().startswith(("http://", "https://", "//"))
        schema_path = "/" + openapi_url.lstrip("/")
        paths = [cfg.docs_url, "/swagger", cfg.redoc_url]
        if not remote_schema:
            paths.append(schema_path)
        for path in paths:
            if not isinstance(path, str) or not path.startswith("/") or any(char in path for char in "{}?#"):
                raise ValueError("Documentation routes must be static absolute paths")
        keys = [self._key(path) for path in paths]
        if len(set(keys)) != len(keys):
            raise ValueError("Documentation URLs must have distinct paths, including /swagger")
        for route in app.routes:
            if route["method"].upper() == "GET" and self._key(route["path"]) in keys:
                raise ValueError(f"GET {route['path']!r} conflicts with a documentation route; configure a different docs URL")

        def get_openapi_schema(request: Request):
            schema = gen.get_openapi_schema()
            root_path = request.scope.get("root_path", "").rstrip("/")
            if root_path and not cfg.servers:
                return {**schema, "servers": [{"url": root_path}]}
            return schema

        def schema_url(request):
            url = openapi_url
            if url.lower().startswith(("http://", "https://", "//")):
                return url
            return request.scope.get("root_path", "").rstrip("/") + "/" + url.lstrip("/")

        def get_scalar_docs(request: Request):
            return HTMLResponse(gen.get_scalar_html(schema_url(request), cfg.info.title))

        def get_swagger_ui(request: Request):
            return HTMLResponse(gen.get_swagger_ui_html(schema_url(request), cfg.info.title))

        def get_redoc(request: Request):
            return HTMLResponse(gen.get_redoc_html(schema_url(request), cfg.info.title))

        routes = [(cfg.docs_url, get_scalar_docs), ("/swagger", get_swagger_ui), (cfg.redoc_url, get_redoc)]
        if not remote_schema:
            routes.append((schema_path, get_openapi_schema))
        prepared = [(path, endpoint, app._installer.prepare(path, endpoint, include_in_schema=False))
                    for path, endpoint in routes]
        # No user code or signature/schema validation runs during publication.
        for path, endpoint, handler in prepared:
            app._trie.add(path, "GET", handler)
            app._registry.add(path, "GET", endpoint, include_in_schema=False)
        self._paths = frozenset(keys)
        self._setup_done = True
