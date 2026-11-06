"""
tachyon routes - List all registered routes in the app.
"""

import typer
import json
from ..utils import load_app


def list_routes(app_path: str, *, json_output=False, include_websockets=False) -> None:
    """Import the app and print all registered routes."""
    tachyon_app = load_app(app_path)

    routes = getattr(tachyon_app, "routes", None)
    if routes is None:
        typer.secho(
            "❌ Object doesn't look like a Tachyon app (no .routes attribute)",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    routes = [dict(route) for route in routes]
    if include_websockets:
        from starlette.routing import WebSocketRoute, Mount
        def delegated(items, prefix=""):
            for item in items:
                if isinstance(item, WebSocketRoute):
                    routes.append({"method": "WS", "path": prefix + item.path, "name": item.name})
                elif isinstance(item, Mount):
                    delegated(item.routes, prefix + item.path)
        delegated(getattr(getattr(tachyon_app, "_router", None), "routes", ()))
    if json_output:
        typer.echo(json.dumps({"schema_version": 1, "routes": [
            {"method": route.get("method"), "path": route.get("path"), "name": route.get("name", ""),
             "protocol": "websocket" if route.get("method") == "WS" else "http"}
            for route in sorted(routes, key=lambda r: (r.get("path", ""), r.get("method", "")))
        ]}))
        return
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
