"""Shared utilities for LLM response processing."""

from __future__ import annotations

import re


def strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from LLM responses."""
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()
