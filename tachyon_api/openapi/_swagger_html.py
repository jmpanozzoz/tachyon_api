# Renders the Swagger UI HTML page that fetches the OpenAPI spec from `openapi_url`.

import html

from ._safe_json import _safe_json


class SwaggerUIRenderer:
    """Renders the Swagger UI page for a given OpenAPI URL + title."""

    __slots__ = ("_config",)

    def __init__(self, config) -> None:
        self._config = config

    def render(self, openapi_url: str, title: str) -> str:
        cfg = self._config
        swagger_ui_parameters = cfg.swagger_ui_parameters or {}
        params_json = _safe_json(swagger_ui_parameters)
        safe_url = _safe_json(openapi_url)
        safe_title = html.escape(title)

        return f"""<!DOCTYPE html>
<html>
<head>
    <link type="text/css" rel="stylesheet" href="{cfg.swagger_css_url}">
    <link rel="shortcut icon" href="{cfg.swagger_favicon_url}">
    <title>{safe_title}</title>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="{cfg.swagger_js_url}"></script>
    <script>
    const ui = SwaggerUIBundle({{
        url: {safe_url},
        dom_id: '#swagger-ui',
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIBundle.presets.standalone
        ],
        layout: "BaseLayout",
        ...{params_json}
    }})
    </script>
</body>
</html>"""
