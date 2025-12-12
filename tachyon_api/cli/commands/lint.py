"""
tachyon lint - Code quality tools (ruff wrapper)
"""

import typer
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List

app = typer.Typer(no_args_is_help=True)


def _check_ruff_installed() -> bool:
    """Check if ruff is installed."""
    return shutil.which("ruff") is not None


def _run_ruff(args: List[str], check: bool = True) -> int:
    """Run ruff with given arguments."""
    if not _check_ruff_installed():
        typer.secho(
            "❌ ruff is not installed. Install it with: pip install ruff",
            fg=typer.colors.RED
        )
        raise typer.Exit(1)
    
    cmd = ["ruff"] + args
    result = subprocess.run(cmd)
    return result.returncode


@app.command()
def check(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to check (default: current directory)"
    ),
    fix: bool = typer.Option(
        False, "--fix", "-f",
        help="Automatically fix issues where possible"
    ),
    watch: bool = typer.Option(
        False, "--watch", "-w",
        help="Watch for changes and re-run"
    ),
):
    """
    🔍 Check code for linting issues.
    
    Example:
        tachyon lint check
        tachyon lint check --fix
        tachyon lint check ./src --watch
    """
    target = str(path) if path else "."
    
    args = ["check", target]
    
    if fix:
        args.append("--fix")
    
    if watch:
        args.append("--watch")
    
    typer.echo(f"🔍 Checking: {target}\n")
    exit_code = _run_ruff(args)
    
    if exit_code == 0:
        typer.secho("\n✅ No issues found!", fg=typer.colors.GREEN)
    
    raise typer.Exit(exit_code)


@app.command()
def fix(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to fix (default: current directory)"
    ),
    unsafe: bool = typer.Option(
        False, "--unsafe",
        help="Apply unsafe fixes as well"
    ),
):
    """
    🔧 Automatically fix linting issues.
    
    Example:
        tachyon lint fix
        tachyon lint fix ./src
        tachyon lint fix --unsafe
    """
    target = str(path) if path else "."
    
    args = ["check", target, "--fix"]
    
    if unsafe:
        args.append("--unsafe-fixes")
    
    typer.echo(f"🔧 Fixing: {target}\n")
    exit_code = _run_ruff(args)
    
    if exit_code == 0:
        typer.secho("\n✅ All fixable issues resolved!", fg=typer.colors.GREEN)
    
    raise typer.Exit(exit_code)


@app.command()
def format(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to format (default: current directory)"
    ),
    check_only: bool = typer.Option(
        False, "--check",
        help="Check formatting without making changes"
    ),
    diff: bool = typer.Option(
        False, "--diff",
        help="Show diff of formatting changes"
    ),
):
    """
    🎨 Format code using ruff formatter.
    
    Example:
        tachyon lint format
        tachyon lint format --check
        tachyon lint format --diff
    """
    target = str(path) if path else "."
    
    args = ["format", target]
    
    if check_only:
        args.append("--check")
    
    if diff:
        args.append("--diff")
    
    typer.echo(f"🎨 Formatting: {target}\n")
    exit_code = _run_ruff(args)
    
    if exit_code == 0 and not check_only:
        typer.secho("\n✅ Formatting complete!", fg=typer.colors.GREEN)
    elif exit_code == 0 and check_only:
        typer.secho("\n✅ Code is properly formatted!", fg=typer.colors.GREEN)
    
    raise typer.Exit(exit_code)


@app.command()
def all(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to check and format (default: current directory)"
    ),
    fix: bool = typer.Option(
        True, "--fix/--no-fix",
        help="Auto-fix issues"
    ),
):
    """
    🚀 Run all quality checks: lint + format.
    
    Example:
        tachyon lint all
        tachyon lint all --no-fix
    """
    target = str(path) if path else "."
    
    typer.echo(f"🚀 Running all quality checks on: {target}\n")
    
    # Run linting
    typer.echo("─" * 40)
    typer.echo("🔍 Step 1: Linting")
    typer.echo("─" * 40)
    
    lint_args = ["check", target]
    if fix:
        lint_args.append("--fix")
    
    lint_code = _run_ruff(lint_args)
    
    # Run formatting
    typer.echo("\n" + "─" * 40)
    typer.echo("🎨 Step 2: Formatting")
    typer.echo("─" * 40)
    
    format_args = ["format", target]
    format_code = _run_ruff(format_args)
    
    # Summary
    typer.echo("\n" + "═" * 40)
    if lint_code == 0 and format_code == 0:
        typer.secho("✅ All checks passed!", fg=typer.colors.GREEN, bold=True)
    else:
        typer.secho("⚠️  Some issues found", fg=typer.colors.YELLOW, bold=True)
    
    raise typer.Exit(max(lint_code, format_code))
