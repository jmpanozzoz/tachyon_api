"""
tachyon openapi - OpenAPI schema utilities
"""

import typer
import json
from pathlib import Path
from typing import Optional

from ..utils import load_app as _load_app

app = typer.Typer(no_args_is_help=True)


@app.command()
def export(
    app_path: str = typer.Argument(
        ..., help="App path in format 'module:attribute' (e.g., 'app:app')"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (default: stdout)"
    ),
    indent: int = typer.Option(2, "--indent", "-i", help="JSON indentation level"),
):
    """
    📄 Export OpenAPI schema to JSON.

    Example:
        tachyon openapi export app:app
        tachyon openapi export app:app -o openapi.json
        tachyon openapi export app:app | jq .
    """
    typer.echo(f"📄 Loading app from: {app_path}", err=True)

    app_instance = _load_app(app_path)

    # Get OpenAPI schema
    try:
        schema = app_instance.openapi_generator.get_openapi_schema()
    except AttributeError:
        typer.secho(
            "❌ The loaded object doesn't appear to be a Tachyon app",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Convert to JSON
    json_output = json.dumps(schema, indent=indent, ensure_ascii=False)

    if output:
        output.write_text(json_output)
        typer.echo(f"✅ Schema exported to: {output}", err=True)
    else:
        typer.echo(json_output)


@app.command()
def validate(
    schema_path: Path = typer.Argument(..., help="Path to OpenAPI schema file"),
):
    """
    ✅ Check basic OpenAPI structure (not full specification validation).

    Example:
        tachyon openapi validate openapi.json
    """
    if not schema_path.exists():
        typer.secho(f"❌ File not found: {schema_path}", fg=typer.colors.RED)
        raise typer.Exit(1)

    try:
        content = schema_path.read_text()
        schema = json.loads(content)

        if not isinstance(schema, dict):
            typer.secho(
                "❌ Invalid schema: root must be an object", fg=typer.colors.RED
            )
            raise typer.Exit(1)
        required_fields = ["openapi", "info", "paths"]
        missing = [f for f in required_fields if f not in schema]

        if missing:
            typer.secho(
                f"❌ Invalid schema: missing required fields: {missing}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        info = schema["info"]
        if (
            not isinstance(schema["openapi"], str)
            or not schema["openapi"].startswith("3.")
            or not isinstance(info, dict)
            or not isinstance(info.get("title"), str)
            or not isinstance(info.get("version"), str)
            or not isinstance(schema["paths"], dict)
            or any(
                not isinstance(path, str)
                or not path.startswith("/")
                or not isinstance(item, dict)
                for path, item in schema["paths"].items()
            )
        ):
            typer.secho(
                "❌ Invalid schema: incorrect basic field types or values",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
        typer.secho(
            "✅ Basic structure check passed (not full OpenAPI validation).",
            fg=typer.colors.GREEN,
        )
        typer.echo(f"   OpenAPI version: {schema.get('openapi')}")
        typer.echo(f"   Title: {schema.get('info', {}).get('title')}")
        typer.echo(f"   Paths: {len(schema.get('paths', {}))}")

    except json.JSONDecodeError as e:
        typer.secho(f"❌ Invalid JSON: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
