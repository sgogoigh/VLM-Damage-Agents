"""Load prompt templates and expose their version tags (used for cache keys)."""
from __future__ import annotations

import re
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_VERSION_RE = re.compile(r"PROMPT_VERSION:\s*([\w.\-]+)")


def load(name: str) -> tuple[str, str]:
    """Return (template_text, version) for prompts/<name>.md."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    m = _VERSION_RE.search(text)
    version = m.group(1) if m else f"{name}_unknown"
    return text, version


def render(template: str, **fields: str) -> str:
    """Substitute {placeholders} without disturbing literal JSON braces.

    Unlike str.format(), this only replaces the exact {key} tokens we pass in,
    so the example JSON schemas embedded in the prompt files are left untouched.
    """
    out = template
    for key, value in fields.items():
        out = out.replace("{" + key + "}", str(value))
    return out


IMAGE_ANALYSIS_TEMPLATE, IMAGE_ANALYSIS_VERSION = load("image_analysis")
CLAIM_PARSER_TEMPLATE, CLAIM_PARSER_VERSION = load("claim_parser")
