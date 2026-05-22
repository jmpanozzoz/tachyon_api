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
