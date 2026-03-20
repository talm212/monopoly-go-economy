"""Tests for run_async — safe async-to-sync helper.

Verifies:
- Successfully runs a simple async coroutine and returns result
- Propagates exceptions from the coroutine
"""

from __future__ import annotations

import pytest

from src.ui.async_helper import run_async


# ---------------------------------------------------------------------------
# Test coroutines
# ---------------------------------------------------------------------------


async def _return_value(val: int) -> int:
    """Simple async coroutine that returns a value."""
    return val


async def _raise_error(msg: str) -> None:
    """Async coroutine that raises a ValueError."""
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunAsync:
    """Verify run_async bridges async coroutines to sync context."""

    def test_returns_coroutine_result(self) -> None:
        result = run_async(_return_value(42))
        assert result == 42

    def test_returns_different_values(self) -> None:
        assert run_async(_return_value(0)) == 0
        assert run_async(_return_value(-1)) == -1
        assert run_async(_return_value(999)) == 999

    def test_propagates_value_error(self) -> None:
        with pytest.raises(ValueError, match="test error"):
            run_async(_raise_error("test error"))

    def test_propagates_runtime_error(self) -> None:
        async def _raise_runtime() -> None:
            raise RuntimeError("runtime failure")

        with pytest.raises(RuntimeError, match="runtime failure"):
            run_async(_raise_runtime())
