"""
tachyon new - Create new project with clean architecture
"""

import typer
from pathlib import Path
from typing import Optional

from ..templates import ProjectTemplates


def create_project(name: str, parent_path: Optional[Path] = None):
    """
    Create a new Tachyon project with clean architecture structure.

    Structure:
        my-api/
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
    # Determine project path
    base_path = parent_path or Path.cwd()
    project_path = base_path / name

    # Check if already exists
    if project_path.exists():
        typer.secho(f"❌ Directory '{name}' already exists!", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo(f"\n🚀 Creating Tachyon project: {typer.style(name, bold=True)}\n")

    # Create directory structure
    directories = [
        project_path,
        project_path / "modules",
        project_path / "shared",
        project_path / "tests",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        typer.echo(f"  📁 Created {directory.relative_to(base_path)}/")

    # Create files
    files = {
        "app.py": ProjectTemplates.APP,
        "config.py": ProjectTemplates.CONFIG,
        "requirements.txt": ProjectTemplates.REQUIREMENTS,
        "modules/__init__.py": ProjectTemplates.MODULES_INIT,
        "shared/__init__.py": ProjectTemplates.SHARED_INIT,
        "shared/exceptions.py": ProjectTemplates.SHARED_EXCEPTIONS,
        "shared/dependencies.py": ProjectTemplates.SHARED_DEPENDENCIES,
        "tests/__init__.py": "",
        "tests/conftest.py": ProjectTemplates.TESTS_CONFTEST,
    }

    for file_path, content in files.items():
        full_path = project_path / file_path
        full_path.write_text(content)
        typer.echo(f"  📄 Created {file_path}")

    # Success message
    typer.echo(
        f"\n✅ Project {typer.style(name, bold=True, fg=typer.colors.GREEN)} created successfully!"
    )
    typer.echo("\n📖 Next steps:")
    typer.echo(f"   cd {name}")
    typer.echo("   pip install -r requirements.txt")
    typer.echo("   python app.py")
    typer.echo("\n   Then generate your first service:")
    typer.echo("   tachyon g service users")
    typer.echo()
