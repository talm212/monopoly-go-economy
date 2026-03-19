"""Reusable bar chart component for rendering distribution data."""

from __future__ import annotations

import logging

import altair as alt
import polars as pl
import streamlit as st

logger = logging.getLogger(__name__)


def render_distribution_chart(
    distribution: dict[str, int],
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    """Render a bar chart from a distribution dictionary.

    Args:
        distribution: Mapping of category labels to count values.
        title: Chart title displayed above the chart.
        x_label: Label for the x-axis (categories).
        y_label: Label for the y-axis (counts/values).
    """
    if not distribution:
        logger.debug("Empty distribution provided to render_distribution_chart; skipping")
        st.info("No distribution data to display.")
        return

    df = pl.DataFrame(
        {
            x_label: list(distribution.keys()),
            y_label: list(distribution.values()),
        }
    )

    # Preserve the original key ordering via a sort column
    df = df.with_row_index("_sort_order")

    chart = (
        alt.Chart(df)
        .mark_bar(color="#FF6B35")
        .encode(
            x=alt.X(f"{x_label}:N", sort=alt.EncodingSortField(field="_sort_order"), title=x_label),
            y=alt.Y(f"{y_label}:Q", title=y_label),
            tooltip=[
                alt.Tooltip(f"{x_label}:N", title=x_label),
                alt.Tooltip(f"{y_label}:Q", title=y_label, format=","),
            ],
        )
        .properties(title=title, width="container", height=400)
    )

    st.altair_chart(chart, use_container_width=True)
