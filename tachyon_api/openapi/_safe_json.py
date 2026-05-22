# JSON-encode a value safe for embedding inside a <script> tag of an HTML page.
# Escapes <, >, and & so that the browser cannot interpret them as HTML tags
# even when the encoded string contains valid JSON.

import json
from typing import Any


def _safe_json(value: Any) -> str:
    return (
        json.dumps(value, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
