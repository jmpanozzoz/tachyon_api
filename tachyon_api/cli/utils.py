"""Shared helpers for CLI commands."""

import keyword
import re

import typer


def validate_name(name: str, kind: str = "module") -> str:
    """Normalise and validate a project/component name.

    Converts hyphens to underscores, rejects Python keywords and identifiers
    that start with a digit or contain invalid characters.  Returns the
    normalised snake_case name.
    """
    normalised = name.replace("-", "_").lower()

    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", normalised):
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


def normalize_app_target(target: str) -> str:
    """Accept module or module:attribute, defaulting the attribute to app."""
    module, separator, attribute = target.partition(":")
    if (
        not module
        or any(not part.isidentifier() for part in module.split("."))
        or (separator and (not attribute.isidentifier()))
    ):
        typer.secho(
            "❌ Invalid app path format. Use 'module:attribute'", fg=typer.colors.RED
        )
        raise typer.Exit(1)
    return f"{module}:{attribute if separator else 'app'}"


def load_app(target: str):
    import importlib
    import sys
    from pathlib import Path

    module_name, attribute = normalize_app_target(target).split(":")
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    try:
        return getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError) as exc:
        typer.secho(
            f"❌ Module or attribute not found while loading {target}: {exc}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1) from exc
