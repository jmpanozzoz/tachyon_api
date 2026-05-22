"""
tachyon new - Create new project with clean architecture
"""

import typer
from pathlib import Path
from typing import Optional

from ..templates import ProjectTemplates
from ..utils import validate_name as _validate_name


def create_project(name: str, parent_path: Optional[Path] = None):
    """
    Create a new Tachyon project with clean architecture structure.

    Structure:
        my-api/
        ├── .env.example
        ├── app.py
        ├── config.py
        ├── requirements.txt
        ├── modules/
        │   └── __init__.py
        ├── shared/
        │   ├── __init__.py
        │   ├── exceptions.py
        │   └── dependencies.py
        └── tests/
            ├── __init__.py
            └── conftest.py
    """
    name = _validate_name(name)

    base_path = parent_path or Path.cwd()
    project_path = base_path / name

    if project_path.exists():
        typer.secho(f"❌ Directory '{name}' already exists!", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo(f"\n🚀 Creating Tachyon project: {typer.style(name, bold=True)}\n")

    # Create directory structure
    for directory in [project_path, project_path / "modules",
                      project_path / "shared", project_path / "tests"]:
        directory.mkdir(parents=True, exist_ok=True)
        typer.echo(f"  📁 Created {directory.relative_to(base_path)}/")

    # Create files
    files = {
        ".env.example":           ProjectTemplates.ENV_EXAMPLE,
        "app.py":                 ProjectTemplates.APP,
        "config.py":              ProjectTemplates.CONFIG,
        "requirements.txt":       ProjectTemplates.REQUIREMENTS,
        "modules/__init__.py":    ProjectTemplates.MODULES_INIT,
        "shared/__init__.py":     ProjectTemplates.SHARED_INIT,
        "shared/exceptions.py":   ProjectTemplates.SHARED_EXCEPTIONS,
        "shared/dependencies.py": ProjectTemplates.SHARED_DEPENDENCIES,
        "tests/__init__.py":      "",
        "tests/conftest.py":      ProjectTemplates.TESTS_CONFTEST,
    }

    for file_path, content in files.items():
        (project_path / file_path).write_text(content)
        typer.echo(f"  📄 Created {file_path}")

    # Success message
    typer.echo(
        f"\n✅ Project {typer.style(name, bold=True, fg=typer.colors.GREEN)} created successfully!"
    )
    typer.echo(f"\n{'─'*50}")
    typer.echo("📖 Next steps:\n")
    typer.secho("  1. Enter the project directory:", fg=typer.colors.BRIGHT_WHITE)
    typer.secho(f"     cd {name}", fg=typer.colors.CYAN)
    typer.echo()
    typer.secho("  2. Copy .env and install dependencies:", fg=typer.colors.BRIGHT_WHITE)
    typer.secho("     cp .env.example .env", fg=typer.colors.CYAN)
    typer.secho("     pip install -r requirements.txt", fg=typer.colors.CYAN)
    typer.echo()
    typer.secho("  3. Start the server:", fg=typer.colors.BRIGHT_WHITE)
    typer.secho("     tachyon run", fg=typer.colors.CYAN)
    typer.secho("     → API:   http://localhost:8000", fg=typer.colors.GREEN)
    typer.secho("     → Docs:  http://localhost:8000/docs", fg=typer.colors.GREEN)
    typer.echo()
    typer.secho("  4. Generate your first module:", fg=typer.colors.BRIGHT_WHITE)
    typer.secho("     tachyon g service users --crud", fg=typer.colors.CYAN)
    typer.secho("     Then register it in app.py:", fg=typer.colors.BRIGHT_BLACK)
    typer.secho("     from modules.users import router as users_router", fg=typer.colors.BRIGHT_BLACK)
    typer.secho("     app.include_router(users_router)", fg=typer.colors.BRIGHT_BLACK)
    typer.echo()
    typer.secho("  5. Run tests:", fg=typer.colors.BRIGHT_WHITE)
    typer.secho("     pytest tests/ -v", fg=typer.colors.CYAN)
    typer.echo(f"{'─'*50}\n")
