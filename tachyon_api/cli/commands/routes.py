"""
tachyon routes - List all registered routes in the app.
"""

import sys
import typer
from pathlib import Path


def list_routes(app_path: str) -> None:
    """Import the app and print all registered routes."""
    # Add cwd to sys.path so local modules resolve
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # Parse "module:attribute" or bare "module"
    if ":" in app_path:
        module_str, attr = app_path.rsplit(":", 1)
    else:
        module_str, attr = app_path, "app"

    try:
        import importlib
        module = importlib.import_module(module_str)
    except ModuleNotFoundError as e:
        typer.secho(f"❌ Module not found: {module_str}\n   {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    tachyon_app = getattr(module, attr, None)
    if tachyon_app is None:
        typer.secho(f"❌ Attribute '{attr}' not found in '{module_str}'", fg=typer.colors.RED)
        raise typer.Exit(1)

    routes = getattr(tachyon_app, "routes", None)
    if routes is None:
        typer.secho("❌ Object doesn't look like a Tachyon app (no .routes attribute)", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not routes:
        typer.secho("ℹ No routes registered.", fg=typer.colors.YELLOW)
        return

    # Column widths
    method_w = 8
    path_w   = max((len(r.get("path", "")) for r in routes), default=10) + 2

    header = f"  {'METHOD':<{method_w}}  {'PATH':<{path_w}}  NAME"
    typer.echo(f"\n{typer.style('Registered routes:', bold=True)}")
    typer.echo("  " + "─" * (method_w + path_w + 20))
    typer.echo(header)
    typer.echo("  " + "─" * (method_w + path_w + 20))

    METHOD_COLORS = {
        "GET":    typer.colors.GREEN,
        "POST":   typer.colors.BLUE,
        "PUT":    typer.colors.YELLOW,
        "PATCH":  typer.colors.CYAN,
        "DELETE": typer.colors.RED,
    }

    for route in sorted(routes, key=lambda r: (r.get("path", ""), r.get("method", ""))):
        method = route.get("method", "?").upper()
        path   = route.get("path", "?")
        name   = route.get("name", "")
        color  = METHOD_COLORS.get(method, typer.colors.WHITE)
        method_str = typer.style(f"{method:<{method_w}}", fg=color, bold=True)
        typer.echo(f"  {method_str}  {path:<{path_w}}  {name}")

    typer.echo(f"\n  {len(routes)} route(s) total.\n")
