"""Tests for strip_markdown_fences — LLM response processing utility.

Verifies:
- Strips ```json ... ``` wrapper
- Strips ``` ... ``` without language tag
- No-op when no fences present
- Empty string handling
"""

from __future__ import annotations

import pytest

from src.infrastructure.llm.utils import strip_markdown_fences

# ---------------------------------------------------------------------------
# Stripping code fences
# ---------------------------------------------------------------------------


class TestStripMarkdownFences:
    """Verify markdown fence removal from LLM responses."""

    def test_strips_json_fenced_block(self) -> None:
        text = '```json\n{"key": "value"}\n```'
        result = strip_markdown_fences(text)
        assert result == '{"key": "value"}'

    def test_strips_plain_fenced_block(self) -> None:
        text = '```\n{"key": "value"}\n```'
        result = strip_markdown_fences(text)
        assert result == '{"key": "value"}'

    def test_noop_when_no_fences(self) -> None:
        text = '{"key": "value"}'
        result = strip_markdown_fences(text)
        assert result == '{"key": "value"}'

    def test_empty_string_returns_empty(self) -> None:
        result = strip_markdown_fences("")
        assert result == ""

    def test_strips_surrounding_whitespace_without_fences(self) -> None:
        text = '  \n{"key": "value"}\n  '
        result = strip_markdown_fences(text)
        assert result == '{"key": "value"}'

    def test_multiline_json_inside_fences(self) -> None:
        text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        result = strip_markdown_fences(text)
        assert result == '{\n  "a": 1,\n  "b": 2\n}'

    @pytest.mark.parametrize(
        ("fenced_text", "expected"),
        [
            ('```json\n[1, 2, 3]\n```', "[1, 2, 3]"),
            ('```\nplain text\n```', "plain text"),
            ("no fences at all", "no fences at all"),
        ],
        ids=["json-array", "plain-text", "no-fences"],
    )
    def test_parametrized_cases(self, fenced_text: str, expected: str) -> None:
        assert strip_markdown_fences(fenced_text) == expected
