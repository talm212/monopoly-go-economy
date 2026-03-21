"""Shared formatting utilities for the UI layer.

Provides number and delta formatting functions used across multiple
UI components (comparison views, optimizer comparisons, etc.).
"""

from __future__ import annotations

import math


def fmt(value: float) -> str:
    """Format a number -- drop .00 for whole numbers."""
    if not math.isfinite(value):
        return f"{value}"
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def fmt_delta(value: float) -> str | None:
    """Format a delta value -- drop .00 for whole numbers, None if zero."""
    if value == 0:
        return None
    if value == int(value):
        return f"{int(value):+,}"
    return f"{value:+,.2f}"
