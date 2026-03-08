"""Utilities for loading benchmark prompt templates."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PROMPT_DIR = _ROOT / "prompts"


@lru_cache(maxsize=None)
def load_prompt(prompt_name: str) -> str:
    """Read and cache a prompt template from the prompts directory."""
    if not prompt_name.endswith(".md"):
        prompt_name = f"{prompt_name}.md"
    prompt_path = _PROMPT_DIR / prompt_name
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file {prompt_path} not found.")
    return prompt_path.read_text(encoding="utf-8")
