"""
Tachyon CLI - Main entry point

Commands:
- tachyon new <project>     Create new project
- tachyon generate          Generate components (alias: g)
- tachyon openapi           OpenAPI utilities
- tachyon lint              Code quality (ruff wrapper)
"""

import typer
from typing import Optional
from pathlib import Path

from .commands import generate, openapi, lint

app = typer.Typer(
    name="tachyon",
    help="🚀 Tachyon CLI - Fast API development toolkit",
    add_completion=False,
    no_args_is_help=True,
)

# Register sub-commands
app.add_typer(
    generate.app,
    name="generate",
    help="Generate components (service, controller, etc.)",
)
app.add_typer(generate.app, name="g", help="Alias for 'generate'", hidden=True)
app.add_typer(openapi.app, name="openapi", help="OpenAPI schema utilities")
app.add_typer(lint.app, name="lint", help="Code quality tools (ruff wrapper)")


@app.command()
def new(
    name: str = typer.Argument(..., help="Project name"),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Parent directory for the project (default: current directory)",
    ),
):
    """
    🏗️  Create a new Tachyon project with clean architecture.

    Example:
        tachyon new my-api
        tachyon new my-api --path ./projects
    """
    from .commands.new import create_project

    create_project(name, path)


@app.command()
def version():
    """Show Tachyon version."""
    try:
        from importlib.metadata import version as _v
        ver = _v("tachyon-api")
    except Exception:
        ver = "dev"
    typer.echo(f"Tachyon API v{ver}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
