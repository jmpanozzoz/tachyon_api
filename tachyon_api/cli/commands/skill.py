"""
tachyon install-skill - Install Tachyon AI context for coding assistants.

Generates the appropriate context/rules files so AI agents (Claude Code,
Cursor, GitHub Copilot, OpenCode, Codex, etc.) understand how to write
correct Tachyon API code.
"""

import typer
from pathlib import Path

from ..templates.ai_skill import (
    cursor_rules,
    claude_md_snippet,
    copilot_instructions,
    opencode_rules,
    agents_md,
)


def _write(path: Path, content: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    start = "<!-- tachyon-api:begin -->"
    end = "<!-- tachyon-api:end -->"
    existing = path.read_text() if path.exists() else ""
    section = f"{start}\n{content.rstrip()}\n{end}"
    if start in existing or end in existing:
        if (
            existing.count(start) != 1
            or existing.count(end) != 1
            or existing.index(end) < existing.index(start)
        ):
            typer.secho(
                f"  ⚠ {label} — malformed managed section; left unchanged",
                fg=typer.colors.YELLOW,
            )
            return
        first = existing.index(start)
        last = existing.index(end) + len(end)
        updated = existing[:first] + section + existing[last:]
    else:
        updated = existing + ("\n\n" if existing else "") + section + "\n"
    if updated == existing:
        typer.secho(f"  ✓ {label} — already up to date", fg=typer.colors.BRIGHT_BLACK)
        return
    path.write_text(updated)
    typer.secho(f"  📄 Updated {label}", fg=typer.colors.GREEN)


def install_skill(
    cursor: bool,
    claude: bool,
    copilot: bool,
    opencode: bool,
    agents: bool,
    all_tools: bool,
    output_dir: Path,
) -> None:
    do_all = all_tools or not any([cursor, claude, copilot, opencode, agents])

    typer.echo(
        f"\n🤖 Installing Tachyon AI skill in: {typer.style(str(output_dir), bold=True)}\n"
    )

    if do_all or cursor:
        _write(
            output_dir / ".cursorrules",
            cursor_rules(),
            ".cursorrules  (Cursor AI)",
        )

    if do_all or claude:
        _write(
            output_dir / "CLAUDE.md", claude_md_snippet(), "CLAUDE.md  (Claude Code)"
        )

    if do_all or copilot:
        _write(
            output_dir / ".github" / "copilot-instructions.md",
            copilot_instructions(),
            ".github/copilot-instructions.md  (GitHub Copilot)",
        )

    if do_all or opencode:
        _write(
            output_dir / ".opencode" / "rules.md",
            opencode_rules(),
            ".opencode/rules.md  (OpenCode)",
        )

    if do_all or agents:
        _write(
            output_dir / "AGENTS.md",
            agents_md(),
            "AGENTS.md  (Codex / Aider / generic agents)",
        )

    typer.echo("\n✅ Done! The AI context files teach your assistant:\n")
    typer.secho(
        "   • Tachyon syntax and key differences from FastAPI", fg=typer.colors.CYAN
    )
    typer.secho(
        "   • Body() requirement, Struct usage, DI patterns", fg=typer.colors.CYAN
    )
    typer.secho(
        "   • CLI commands (tachyon run, generate, routes, ...)", fg=typer.colors.CYAN
    )
    typer.secho("   • Common anti-patterns to avoid", fg=typer.colors.CYAN)
    typer.echo()
