"""
Tachyon CLI - Main entry point

Commands:
- tachyon new <project>     Create new project
- tachyon run [app]         Start development / production server
- tachyon generate          Generate components (alias: g)
- tachyon routes [app]      List all registered routes
- tachyon openapi           OpenAPI utilities
- tachyon lint              Code quality (ruff wrapper)
- tachyon version           Show version
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

# Sub-command groups
app.add_typer(generate.app, name="generate", help="Generate components (service, controller, etc.)")
app.add_typer(generate.app, name="g",        help="Alias for 'generate'", hidden=True)
app.add_typer(openapi.app,  name="openapi",  help="OpenAPI schema utilities")
app.add_typer(lint.app,     name="lint",     help="Code quality tools (ruff wrapper)")


@app.command()
def new(
    name: str = typer.Argument(..., help="Project name (e.g. my-api)"),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p",
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
def run(
    app_path: str = typer.Argument("app:app", help="ASGI app in 'module:attribute' format"),
    host: str   = typer.Option("0.0.0.0", "--host", "-h", help="Bind host"),
    port: int   = typer.Option(8000,      "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(True,  "--reload/--no-reload", help="Auto-reload on code changes"),
    workers: int = typer.Option(1,     "--workers", "-w", help="Number of worker processes"),
    prod: bool   = typer.Option(False, "--prod",           help="Production mode (no reload, workers=4)"),
    tachyon_server: bool = typer.Option(
        False, "--tachyon-server",
        help="Use TachyonServer for direct transport writes (F12b)",
    ),
):
    """
    ▶  Start the Tachyon development or production server.

    Wraps uvicorn with sensible defaults (uvloop, httptools, reload in dev).

    Example:
        tachyon run
        tachyon run app:app --port 9000
        tachyon run --prod --workers 4
        tachyon run --tachyon-server
    """
    from .commands.run import run_server
    run_server(app_path, host, port, reload, workers, prod, tachyon_server)


@app.command()
def routes(
    app_path: str = typer.Argument("app:app", help="ASGI app in 'module:attribute' format"),
):
    """
    📋 List all registered routes without starting the server.

    Example:
        tachyon routes
        tachyon routes myapp:app
    """
    from .commands.routes import list_routes
    list_routes(app_path)


@app.command("install-skill")
def install_skill(
    cursor:   bool = typer.Option(False, "--cursor",   help="Install for Cursor (.cursorrules)"),
    claude:   bool = typer.Option(False, "--claude",   help="Install for Claude Code (CLAUDE.md)"),
    copilot:  bool = typer.Option(False, "--copilot",  help="Install for GitHub Copilot (.github/copilot-instructions.md)"),
    opencode: bool = typer.Option(False, "--opencode", help="Install for OpenCode (.opencode/rules.md)"),
    agents:   bool = typer.Option(False, "--agents",   help="Install generic AGENTS.md (Codex, Aider, etc.)"),
    all_tools: bool = typer.Option(False, "--all",     help="Install for all tools (default when no flag given)"),
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Target directory (default: current directory)"),
):
    """
    🤖 Install Tachyon AI context for your coding assistant.

    Generates rules/instructions files so AI agents understand Tachyon syntax,
    patterns, and best practices (Body() requirement, Struct vs BaseModel, DI, CLI, etc.).

    Example:
        tachyon install-skill              # installs all tools
        tachyon install-skill --cursor     # only .cursorrules
        tachyon install-skill --claude     # only CLAUDE.md
        tachyon install-skill --copilot    # only .github/copilot-instructions.md
        tachyon install-skill --all        # explicit all
    """
    from .commands.skill import install_skill as _install
    _install(cursor, claude, copilot, opencode, agents, all_tools, path or Path.cwd())


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
