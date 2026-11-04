"""
tachyon routes - List all registered routes in the app.
"""

import typer
from ..utils import load_app


def list_routes(app_path: str) -> None:
    """Import the app and print all registered routes."""
    tachyon_app = load_app(app_path)

    routes = getattr(tachyon_app, "routes", None)
    if routes is None:
        typer.secho(
            "❌ Object doesn't look like a Tachyon app (no .routes attribute)",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if not routes:
        typer.secho("ℹ No routes registered.", fg=typer.colors.YELLOW)
        return

    # Column widths
    method_w = 8
    path_w = max((len(r.get("path", "")) for r in routes), default=10) + 2

    header = f"  {'METHOD':<{method_w}}  {'PATH':<{path_w}}  NAME"
    typer.echo(f"\n{typer.style('Registered routes:', bold=True)}")
    typer.echo("  " + "─" * (method_w + path_w + 20))
    typer.echo(header)
    typer.echo("  " + "─" * (method_w + path_w + 20))

    METHOD_COLORS = {
        "GET": typer.colors.GREEN,
        "POST": typer.colors.BLUE,
        "PUT": typer.colors.YELLOW,
        "PATCH": typer.colors.CYAN,
        "DELETE": typer.colors.RED,
    }

    for route in sorted(routes, key=lambda r: (r.get("path", ""), r.get("method", ""))):
        method = route.get("method", "?").upper()
        path = route.get("path", "?")
        name = route.get("name", "")
        color = METHOD_COLORS.get(method, typer.colors.WHITE)
        method_str = typer.style(f"{method:<{method_w}}", fg=color, bold=True)
        typer.echo(f"  {method_str}  {path:<{path_w}}  {name}")

    typer.echo(f"\n  {len(routes)} route(s) total.\n")
