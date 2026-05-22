# Renders the Scalar API Reference HTML page for the OpenAPI spec.

import html


class ScalarRenderer:
    """Renders the Scalar API Reference page for a given OpenAPI URL + title."""

    __slots__ = ("_config",)

    def __init__(self, config) -> None:
        self._config = config

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
