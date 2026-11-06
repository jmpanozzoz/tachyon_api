"""Read-only diagnostics; importing user applications and networking are opt-in."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from importlib import metadata
import io
import json
import os
import sys

import typer


def diagnose(app_path=None, connect=False):
    checks = []
    def record(code, ok, detail):
        checks.append({"code": code, "ok": ok, "detail": detail})
    record("python", (3, 10) <= sys.version_info[:2] < (3, 14),
           ".".join(map(str, sys.version_info[:3])))
    for package in ("tachyon-api", "starlette", "msgspec", "uvicorn", "typer"):
        try:
            record(package, True, metadata.version(package))
        except metadata.PackageNotFoundError:
            record(package, False, "Install the project's declared requirements")
    if os.getenv("ENVIRONMENT", "development") not in {"development", "test"}:
        record("secret_key", len(os.getenv("SECRET_KEY", "")) >= 32,
               "Production requires an explicit SECRET_KEY of at least 32 characters")
        record("debug", os.getenv("DEBUG", "false").lower() == "false", "Production requires DEBUG=false")
    if app_path:
        # Imported user code can have effects. Capture its output to avoid
        # leaking environment values through normal JSON diagnostics.
        try:
            from ..utils import load_app
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                application = load_app(app_path)
            record("app_import", callable(application) and hasattr(application, "routes"),
                   "Imported application; lifespan was not started")
        except (Exception, SystemExit) as exc:
            record("app_import", False, f"Import failed ({type(exc).__name__}); inspect application locally")
    if connect:
        checks.extend(asyncio.run(connectivity()))
    return {"schema_version": 1, "ok": all(row["ok"] for row in checks), "checks": checks}


async def connectivity():
    from anyio import fail_after
    checks = []
    for kind, variable in (("postgres", "DATABASE_URL"), ("redis", "REDIS_URL")):
        url = os.getenv(variable)
        if not url:
            checks.append({"code": kind, "ok": False, "detail": f"Set {variable} explicitly"})
            continue
        try:
            if kind == "postgres":
                from sqlalchemy.ext.asyncio import create_async_engine
                from sqlalchemy import text
                engine = create_async_engine(url, connect_args={"timeout": 2, "command_timeout": 2})
                try:
                    with fail_after(3):
                        async with engine.connect() as connection:
                            await connection.execute(text("SELECT 1"))
                finally:
                    await engine.dispose()
            else:
                from redis.asyncio import Redis
                client = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
                try:
                    await client.ping()
                finally:
                    await client.aclose()
            checks.append({"code": kind, "ok": True, "detail": "Connection succeeded"})
        except Exception as exc:
            checks.append({"code": kind, "ok": False,
                           "detail": f"Connection failed ({type(exc).__name__}); check service and configuration"})
    return checks


def doctor(app_path=None, connect=False, json_output=False):
    report = diagnose(app_path, connect)
    if json_output:
        typer.echo(json.dumps(report))
    else:
        for check in report["checks"]:
            typer.echo(f"{'OK' if check['ok'] else 'FAIL'} {check['code']}: {check['detail']}")
    raise typer.Exit(0 if report["ok"] else 1)
