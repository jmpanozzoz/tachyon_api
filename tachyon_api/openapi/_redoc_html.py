# Renders the ReDoc HTML page for the OpenAPI spec.

import html


class RedocRenderer:
    """Renders the ReDoc page for a given OpenAPI URL + title."""

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
