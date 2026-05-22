"""
tachyon generate - Generate components (service, controller, repository, dto, middleware)
"""

import keyword
import re
import typer
from pathlib import Path
from typing import Optional

from ..templates import ServiceTemplates

app = typer.Typer(no_args_is_help=True)


# ── Name helpers ──────────────────────────────────────────────────────────────

def _to_class_name(name: str) -> str:
    return "".join(w.capitalize() for w in name.replace("-", "_").split("_"))


def _to_snake_case(name: str) -> str:
    return name.replace("-", "_").lower()


def _validate_name(name: str, kind: str = "module") -> str:
    """Normalise and validate a component name."""
    normalised = _to_snake_case(name)

    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', normalised):
        typer.secho(
            f"❌ '{name}' is not a valid Python identifier for a {kind} name.\n"
            f"   Use letters, digits, and underscores only.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if keyword.iskeyword(normalised):
        typer.secho(
            f"❌ '{normalised}' is a Python reserved keyword.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if normalised != name:
        typer.secho(
            f"  ℹ  Name normalised: '{name}' → '{normalised}'",
            fg=typer.colors.BRIGHT_BLACK,
        )

    return normalised


def _create_file(path: Path, content: str, name: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    typer.echo(f"  📄 Created {name}")


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def service(
    name: str = typer.Argument(..., help="Service name (e.g., 'auth', 'users')"),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Base path for modules (default: ./modules)"
    ),
    no_tests: bool = typer.Option(False, "--no-tests", help="Skip test file generation"),
    crud: bool = typer.Option(
        False, "--crud",
        help="Generate with full CRUD (list, get, create, update, delete)",
    ),
):
    """
    🔧 Generate a complete service module.

    Creates: controller, service, repository, dto, and tests.

    Example:
        tachyon g service auth
        tachyon g service products --crud
        tachyon g service users --path src/modules
    """
    snake_name = _validate_name(name, "service")
    class_name = _to_class_name(snake_name)

    base_path = path or Path.cwd() / "modules"
    service_path = base_path / snake_name

    if service_path.exists():
        typer.secho(f"❌ Module '{snake_name}' already exists!", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo(f"\n🔧 Generating service: {typer.style(snake_name, bold=True)}\n")

    service_path.mkdir(parents=True, exist_ok=True)
    tests_path = service_path / "tests"
    tests_path.mkdir(exist_ok=True)

    files = {
        "__init__.py":               ServiceTemplates.init(snake_name, class_name),
        f"{snake_name}_controller.py": ServiceTemplates.controller(snake_name, class_name, crud),
        f"{snake_name}_service.py":    ServiceTemplates.service(snake_name, class_name, crud),
        f"{snake_name}_repository.py": ServiceTemplates.repository(snake_name, class_name, crud),
        f"{snake_name}_dto.py":        ServiceTemplates.dto(snake_name, class_name, crud),
    }
    for filename, content in files.items():
        _create_file(service_path / filename, content, filename)

    if not no_tests:
        _create_file(tests_path / "__init__.py", "", "tests/__init__.py")
        _create_file(
            tests_path / f"test_{snake_name}_service.py",
            ServiceTemplates.test_service(snake_name, class_name),
            f"tests/test_{snake_name}_service.py",
        )

    typer.echo(
        f"\n✅ Service {typer.style(snake_name, bold=True, fg=typer.colors.GREEN)} generated!"
    )
    typer.echo("\n📖 Register in app.py:")
    typer.secho(f"   from modules.{snake_name} import router as {snake_name}_router", fg=typer.colors.CYAN)
    typer.secho(f"   app.include_router({snake_name}_router)", fg=typer.colors.CYAN)
    typer.echo()


@app.command()
def controller(
    name: str = typer.Argument(..., help="Controller name"),
    path: Optional[Path] = typer.Option(None, "--path", "-p"),
):
    """
    📡 Generate a controller (router) file.

    Example:
        tachyon g controller users
    """
    snake_name = _validate_name(name, "controller")
    class_name = _to_class_name(snake_name)
    base_path = (path or Path.cwd() / "modules" / snake_name)
    base_path.mkdir(parents=True, exist_ok=True)

    typer.echo(f"\n📡 Generating controller: {snake_name}\n")
    _create_file(
        base_path / f"{snake_name}_controller.py",
        ServiceTemplates.controller(snake_name, class_name, False),
        f"{snake_name}_controller.py",
    )
    typer.echo("\n✅ Controller generated!")


def _do_repository(name: str, path: Optional[Path]) -> None:
    snake_name = _validate_name(name, "repository")
    class_name = _to_class_name(snake_name)
    base_path = path or Path.cwd() / "modules" / snake_name
    base_path.mkdir(parents=True, exist_ok=True)
    typer.echo(f"\n🗄️  Generating repository: {snake_name}\n")
    _create_file(
        base_path / f"{snake_name}_repository.py",
        ServiceTemplates.repository(snake_name, class_name, False),
        f"{snake_name}_repository.py",
    )
    typer.echo("\n✅ Repository generated!")


@app.command("repository")
def repository(
    name: str = typer.Argument(..., help="Repository name"),
    path: Optional[Path] = typer.Option(None, "--path", "-p"),
):
    """🗄️  Generate a repository file.\n\nExample: tachyon g repository users"""
    _do_repository(name, path)


@app.command("repo", hidden=True)
def repo(
    name: str = typer.Argument(..., help="Repository name"),
    path: Optional[Path] = typer.Option(None, "--path", "-p"),
):
    """Alias for 'repository'."""
    _do_repository(name, path)


@app.command()
def dto(
    name: str = typer.Argument(..., help="DTO name"),
    path: Optional[Path] = typer.Option(None, "--path", "-p"),
):
    """
    📦 Generate a DTO (Data Transfer Object) file.

    Example:
        tachyon g dto users
    """
    snake_name = _validate_name(name, "dto")
    class_name = _to_class_name(snake_name)
    base_path = (path or Path.cwd() / "modules" / snake_name)
    base_path.mkdir(parents=True, exist_ok=True)

    typer.echo(f"\n📦 Generating DTO: {snake_name}\n")
    _create_file(
        base_path / f"{snake_name}_dto.py",
        ServiceTemplates.dto(snake_name, class_name, False),
        f"{snake_name}_dto.py",
    )
    typer.echo("\n✅ DTO generated!")


@app.command()
def middleware(
    name: str = typer.Argument(..., help="Middleware name (e.g., 'auth', 'logging')"),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Output directory (default: ./middlewares)"
    ),
):
    """
    🔒 Generate an ASGI middleware skeleton.

    Example:
        tachyon g middleware auth
        tachyon g middleware rate_limit
    """
    snake_name = _validate_name(name, "middleware")
    class_name = _to_class_name(snake_name)
    base_path = path or Path.cwd() / "middlewares"
    base_path.mkdir(parents=True, exist_ok=True)

    filename = f"{snake_name}_middleware.py"
    typer.echo(f"\n🔒 Generating middleware: {snake_name}\n")
    _create_file(
        base_path / filename,
        ServiceTemplates.middleware(snake_name, class_name),
        filename,
    )

    typer.echo(f"\n✅ Middleware {typer.style(class_name + 'Middleware', bold=True, fg=typer.colors.GREEN)} generated!")
    typer.echo("\n📖 Register in app.py:")
    typer.secho(f"   from middlewares.{snake_name}_middleware import {class_name}Middleware", fg=typer.colors.CYAN)
    typer.secho(f"   app.add_middleware({class_name}Middleware)", fg=typer.colors.CYAN)
    typer.echo()
