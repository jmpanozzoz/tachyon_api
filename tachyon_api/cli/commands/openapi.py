"""
tachyon openapi - OpenAPI schema utilities
"""

import typer
import json
import importlib
from pathlib import Path
from typing import Optional

app = typer.Typer(no_args_is_help=True)


def _load_app(app_path: str):
    """
    Load a Tachyon app from module:attribute format.

    Example: "app:app" or "main:application"
    """
    try:
        module_path, attr_name = app_path.split(":")
    except ValueError:
        typer.secho(
            "❌ Invalid app path format. Use 'module:attribute' (e.g., 'app:app')",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    try:
        module = importlib.import_module(module_path)
        app_instance = getattr(module, attr_name)
        return app_instance
    except ModuleNotFoundError as e:
        typer.secho(f"❌ Module not found: {module_path}", fg=typer.colors.RED)
        typer.secho(f"   Error: {e}", fg=typer.colors.YELLOW)
        raise typer.Exit(1)
    except AttributeError:
        typer.secho(
            f"❌ Attribute '{attr_name}' not found in module '{module_path}'",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)


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
    # Add current directory to path for imports
    import sys

    sys.path.insert(0, str(Path.cwd()))

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
    ✅ Validate an OpenAPI schema file.

    Example:
        tachyon openapi validate openapi.json
    """
    if not schema_path.exists():
        typer.secho(f"❌ File not found: {schema_path}", fg=typer.colors.RED)
        raise typer.Exit(1)

    try:
        content = schema_path.read_text()
        schema = json.loads(content)

        # Basic validation
        required_fields = ["openapi", "info", "paths"]
        missing = [f for f in required_fields if f not in schema]

        if missing:
            typer.secho(
                f"❌ Invalid schema: missing required fields: {missing}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        typer.secho("✅ Schema is valid!", fg=typer.colors.GREEN)
        typer.echo(f"   OpenAPI version: {schema.get('openapi')}")
        typer.echo(f"   Title: {schema.get('info', {}).get('title')}")
        typer.echo(f"   Paths: {len(schema.get('paths', {}))}")

    except json.JSONDecodeError as e:
        typer.secho(f"❌ Invalid JSON: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
