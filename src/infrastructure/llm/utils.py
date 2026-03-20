"""Shared utilities for LLM response processing.

The canonical implementation now lives in ``src.application.llm_utils``.
This module re-exports for backwards compatibility.
"""

from __future__ import annotations

from src.application.llm_utils import strip_markdown_fences

__all__ = ["strip_markdown_fences"]
