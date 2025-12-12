"""
tachyon generate - Generate components (service, controller, repository, dto)
"""

import typer
from pathlib import Path
from typing import Optional

from ..templates import ServiceTemplates

app = typer.Typer(no_args_is_help=True)


def _to_class_name(name: str) -> str:
    """Convert snake_case or kebab-case to PascalCase."""
    return "".join(word.capitalize() for word in name.replace("-", "_").split("_"))


def _to_snake_case(name: str) -> str:
    """Ensure name is in snake_case."""
    return name.replace("-", "_").lower()


def _create_file(path: Path, content: str, name: str):
    """Create a file and print status."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    typer.echo(f"  📄 Created {name}")


@app.command()
def service(
    name: str = typer.Argument(..., help="Service name (e.g., 'auth', 'users')"),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p",
        help="Base path for modules (default: ./modules)"
    ),
    no_tests: bool = typer.Option(
        False, "--no-tests",
        help="Skip test file generation"
    ),
    crud: bool = typer.Option(
        False, "--crud",
        help="Generate with basic CRUD operations"
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
    snake_name = _to_snake_case(name)
    class_name = _to_class_name(name)
    
    base_path = path or Path.cwd() / "modules"
    service_path = base_path / snake_name
    
    if service_path.exists():
        typer.secho(f"❌ Module '{snake_name}' already exists!", fg=typer.colors.RED)
        raise typer.Exit(1)
    
    typer.echo(f"\n🔧 Generating service: {typer.style(snake_name, bold=True)}\n")
    
    # Create directory
    service_path.mkdir(parents=True, exist_ok=True)
    tests_path = service_path / "tests"
    tests_path.mkdir(exist_ok=True)
    
    # Generate files
    files = {
        "__init__.py": ServiceTemplates.init(snake_name, class_name),
        f"{snake_name}_controller.py": ServiceTemplates.controller(snake_name, class_name, crud),
        f"{snake_name}_service.py": ServiceTemplates.service(snake_name, class_name, crud),
        f"{snake_name}_repository.py": ServiceTemplates.repository(snake_name, class_name, crud),
        f"{snake_name}_dto.py": ServiceTemplates.dto(snake_name, class_name, crud),
    }
    
    for filename, content in files.items():
        _create_file(service_path / filename, content, filename)
    
    # Generate tests
    if not no_tests:
        _create_file(tests_path / "__init__.py", "", "tests/__init__.py")
        _create_file(
            tests_path / f"test_{snake_name}_service.py",
            ServiceTemplates.test_service(snake_name, class_name),
            f"tests/test_{snake_name}_service.py"
        )
    
    typer.echo(f"\n✅ Service {typer.style(snake_name, bold=True, fg=typer.colors.GREEN)} generated!")
    typer.echo(f"\n📖 Don't forget to register in app.py:")
    typer.echo(f"   from modules.{snake_name} import router as {snake_name}_router")
    typer.echo(f"   app.include_router({snake_name}_router)")
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
    snake_name = _to_snake_case(name)
    class_name = _to_class_name(name)
    
    base_path = path or Path.cwd() / "modules" / snake_name
    base_path.mkdir(parents=True, exist_ok=True)
    
    typer.echo(f"\n📡 Generating controller: {snake_name}\n")
    
    _create_file(
        base_path / f"{snake_name}_controller.py",
        ServiceTemplates.controller(snake_name, class_name, False),
        f"{snake_name}_controller.py"
    )
    
    typer.echo(f"\n✅ Controller generated!")


@app.command("repo")
@app.command("repository")
def repository(
    name: str = typer.Argument(..., help="Repository name"),
    path: Optional[Path] = typer.Option(None, "--path", "-p"),
):
    """
    🗄️  Generate a repository file.
    
    Example:
        tachyon g repository users
        tachyon g repo products
    """
    snake_name = _to_snake_case(name)
    class_name = _to_class_name(name)
    
    base_path = path or Path.cwd() / "modules" / snake_name
    base_path.mkdir(parents=True, exist_ok=True)
    
    typer.echo(f"\n🗄️  Generating repository: {snake_name}\n")
    
    _create_file(
        base_path / f"{snake_name}_repository.py",
        ServiceTemplates.repository(snake_name, class_name, False),
        f"{snake_name}_repository.py"
    )
    
    typer.echo(f"\n✅ Repository generated!")


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
    snake_name = _to_snake_case(name)
    class_name = _to_class_name(name)
    
    base_path = path or Path.cwd() / "modules" / snake_name
    base_path.mkdir(parents=True, exist_ok=True)
    
    typer.echo(f"\n📦 Generating DTO: {snake_name}\n")
    
    _create_file(
        base_path / f"{snake_name}_dto.py",
        ServiceTemplates.dto(snake_name, class_name, False),
        f"{snake_name}_dto.py"
    )
    
    typer.echo(f"\n✅ DTO generated!")
