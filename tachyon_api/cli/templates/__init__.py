"""
CLI Templates for code generation.
"""

from .project import ProjectTemplates
from .service import ServiceTemplates
from .ai_skill import cursor_rules, claude_md_snippet, copilot_instructions, opencode_rules, agents_md

__all__ = [
    "ProjectTemplates",
    "ServiceTemplates",
    "cursor_rules",
    "claude_md_snippet",
    "copilot_instructions",
    "opencode_rules",
    "agents_md",
]
