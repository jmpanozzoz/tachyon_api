"""
tachyon run - Start the development or production server.
"""

import sys
import typer
from pathlib import Path
from typing import Optional


def run_server(
    app_path: str,
    host: str,
    port: int,
    reload: bool,
    workers: int,
    prod: bool,
    tachyon_server: bool,
) -> None:
    """Start uvicorn with sensible Tachyon defaults."""
    try:
        import uvicorn
    except ImportError:
        typer.secho("❌ uvicorn is not installed. Run: pip install uvicorn[standard]", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Resolve app path relative to cwd
    if Path("app.py").exists() and ":" not in app_path:
        app_path = f"{app_path}:{app_path}" if app_path != "app" else "app:app"

    effective_workers = workers if (prod or workers > 1) else 1
    effective_reload = reload and not prod

    kwargs: dict = {
        "app": app_path,
        "host": host,
        "port": port,
        "workers": effective_workers,
        "reload": effective_reload,
        "access_log": not prod,
    }

    # Use uvloop + httptools when available
    try:
        import uvloop  # noqa: F401
        kwargs["loop"] = "uvloop"
    except ImportError:
        pass
    try:
        import httptools  # noqa: F401
        kwargs["http"] = "httptools"
    except ImportError:
        pass

    # Use TachyonServer (F12b) when requested and available
    if tachyon_server:
        try:
            from tachyon_api.server import TachyonHTTPProtocol
            kwargs["http"] = TachyonHTTPProtocol
            typer.secho("  ⚡ TachyonServer active (direct transport write)", fg=typer.colors.CYAN)
        except ImportError:
            typer.secho("  ℹ TachyonServer not available, using standard uvicorn", fg=typer.colors.BRIGHT_BLACK)

    mode = "production" if prod else "development"
    typer.echo(f"\n🚀 Starting Tachyon in {typer.style(mode, bold=True)} mode")
    typer.echo(f"   App:    {app_path}")
    typer.echo(f"   URL:    http://{host}:{port}")
    if not prod:
        typer.echo(f"   Docs:   http://{host}:{port}/docs")
    typer.echo(f"   Reload: {'on' if effective_reload else 'off'}")
    if effective_workers > 1:
        typer.echo(f"   Workers: {effective_workers}")
    typer.echo()

    uvicorn.run(**kwargs)
