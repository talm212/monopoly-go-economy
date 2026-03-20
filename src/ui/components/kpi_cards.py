"""Reusable KPI metric cards displayed in a responsive column layout."""

from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def _format_value(value: float | int) -> str:
    """Format a numeric value for display — no trailing .00 for whole numbers."""
    if isinstance(value, float):
        if value == int(value):
            return f"{int(value):,}"
        return f"{value:,.2f}"
    return f"{value:,}"


def render_kpi_cards(
    metrics: dict[str, float | int],
    columns: int = 4,
    help_texts: dict[str, str] | None = None,
) -> None:
    """Render KPI metric cards arranged in a column grid.

    Args:
        metrics: Mapping of metric labels to their numeric values.
        columns: Number of columns per row (default 4).
        help_texts: Optional mapping of metric labels to tooltip strings.
    """
    if not metrics:
        logger.debug("No metrics provided to render_kpi_cards; skipping render")
        return

    _help = help_texts or {}
    metric_items = list(metrics.items())
    # Process metrics in batches that fit the column count
    for batch_start in range(0, len(metric_items), columns):
        batch = metric_items[batch_start : batch_start + columns]
        cols = st.columns(len(batch))
        for col, (label, value) in zip(cols, batch, strict=False):
            col.metric(label=label, value=_format_value(value), help=_help.get(label))
