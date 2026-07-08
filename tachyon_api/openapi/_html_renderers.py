# HTML doc-page renderers — Swagger UI, ReDoc, and Scalar.
# Cold path: each page is rendered once per docs request, not per API request.

import html
import json
from typing import Any


def _safe_json(value: Any) -> str:
    """JSON-encode a value safe for embedding inside a <script> tag.

    Escapes <, >, and & so the browser cannot interpret them as HTML tags
    even when the encoded string contains valid JSON.
    """
    return (
        json.dumps(value, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


class _RendererBase:
    __slots__ = ("_config",)

    def __init__(self, config) -> None:
        self._config = config


class SwaggerUIRenderer(_RendererBase):
    """Renders the Swagger UI page for a given OpenAPI URL + title."""

    __slots__ = ()

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


class RedocRenderer(_RendererBase):
    """Renders the ReDoc page for a given OpenAPI URL + title."""

    __slots__ = ()

    def render(self, openapi_url: str, title: str) -> str:
        cfg = self._config
        safe_url = html.escape(openapi_url, quote=True)
        safe_title = html.escape(title)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{safe_title}</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
    body {{
        margin: 0;
        padding: 0;
    }}
    </style>
</head>
<body>
    <redoc spec-url='{safe_url}'></redoc>
    <script src="{cfg.redoc_js_url}"></script>
</body>
</html>"""


class ScalarRenderer(_RendererBase):
    """Renders the Scalar API Reference page for a given OpenAPI URL + title."""

    __slots__ = ()

    def render(self, openapi_url: str, title: str) -> str:
        cfg = self._config
        safe_url = html.escape(openapi_url, quote=True)
        safe_title = html.escape(title)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{safe_title}</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="shortcut icon" href="{cfg.scalar_favicon_url}">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
    </style>
</head>
<body>
    <script
        id="api-reference"
        data-url="{safe_url}"
        src="{cfg.scalar_js_url}"></script>
</body>
</html>"""
