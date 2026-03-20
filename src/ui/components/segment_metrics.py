"""Reusable segment metrics rendering component.

Renders KPI metrics for a player segment (e.g., churn vs non-churn).
Generic enough for any segment comparison across features.
"""

from __future__ import annotations

import polars as pl
import streamlit as st


def render_segment_metrics(segment: pl.DataFrame, label: str) -> None:
    """Render KPI metrics for a player segment (churn / non-churn)."""
    if segment.height == 0:
        st.info(f"No {label} players in this dataset.")
        return

    points_col = segment["total_points"]
    mean_val = float(points_col.mean() or 0.0)
    median_val = float(points_col.median() or 0.0)
    total_val = float(points_col.sum() or 0.0)

    def _fmt_num(v: float) -> str:
        return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"

    st.metric(
        "Player Count", f"{segment.height:,}",
        help=(
            f"Count of players in the **{label}** segment.\n\n"
            f"Segmented by the about_to_churn flag from the uploaded CSV."
        ),
    )
    st.metric(
        "Avg Points / Player", _fmt_num(mean_val),
        help=(
            f"**Calculation:** sum(total_points) / count(players) for {label} segment\n\n"
            f"**Churn boost:** players with about_to_churn=true get "
            f"boosted_p = min(p_success_i * 1.3, 1.0)\n"
            f"so their average is expected to be higher."
        ),
    )
    st.metric(
        "Median Points / Player", _fmt_num(median_val),
        help=(
            f"Middle value of total_points for **{label}** players when sorted.\n\n"
            f"Compare mean vs median to detect skew in the distribution."
        ),
    )
    st.metric(
        "Total Points", _fmt_num(total_val),
        help=(
            f"**Calculation:** sum(total_points) for all {label} players\n\n"
            f"**Parameters:**\n"
            f"- total_points = sum over interactions of "
            f"(cumulative points at success depth * avg_multiplier)"
        ),
    )
