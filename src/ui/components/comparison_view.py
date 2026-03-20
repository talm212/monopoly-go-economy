"""Reusable side-by-side comparison view for two simulation runs.

Works with any simulator's results — compares KPI metrics and
distribution data from run summary dictionaries.
"""

from __future__ import annotations

import logging
from typing import Any

import altair as alt
import polars as pl
import streamlit as st

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CHART_HEIGHT = 400
_COLOR_RUN_A = "#FF6B35"
_COLOR_RUN_B = "#457B9D"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_kpi_metrics(run: dict[str, Any]) -> dict[str, float]:
    """Extract displayable KPI metrics from a run summary."""
    summary = run.get("result_summary", {})
    return {
        "Total Points": float(summary.get("total_points", 0)),
        "Total Interactions": float(summary.get("total_interactions", 0)),
        "Players Above Threshold": float(summary.get("players_above_threshold", 0)),
    }


_COMPARISON_HELP: dict[str, str] = {
    "Total Points": (
        "**Calculation:** sum(total_points) across all players\n\n"
        "**Parameters:**\n"
        "- total_points per player = sum over interactions of "
        "(cumulative points at depth * avg_multiplier)\n\n"
        "Delta = difference between the two runs."
    ),
    "Total Interactions": (
        "**Calculation:** sum(rolls_sink // avg_multiplier) per player\n\n"
        "Each interaction triggers one coin-flip chain of up to max_successes flips."
    ),
    "Players Above Threshold": (
        "**Calculation:** count(players where total_points > threshold)\n\n"
        "Delta = how many more/fewer players crossed the threshold between runs."
    ),
}


def _fmt(value: float) -> str:
    """Format a number — drop .00 for whole numbers."""
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _fmt_delta(value: float) -> str | None:
    """Format a delta value — drop .00 for whole numbers, None if zero."""
    if value == 0:
        return None
    if value == int(value):
        return f"{int(value):+,}"
    return f"{value:+,.2f}"


def _render_metric_comparison(
    metrics_a: dict[str, float],
    metrics_b: dict[str, float],
    label_a: str,
    label_b: str,
) -> None:
    """Render KPI metrics side-by-side with delta indicators."""
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(f"#### {label_a}")
        for label, value_a in metrics_a.items():
            value_b = metrics_b.get(label, 0.0)
            st.metric(
                label=label, value=_fmt(value_a), delta=_fmt_delta(value_a - value_b),
                help=_COMPARISON_HELP.get(label),
            )

    with col_b:
        st.markdown(f"#### {label_b}")
        for label, value_b in metrics_b.items():
            value_a = metrics_a.get(label, 0.0)
            st.metric(
                label=label, value=_fmt(value_b), delta=_fmt_delta(value_b - value_a),
                help=_COMPARISON_HELP.get(label),
            )


def _render_distribution_comparison(
    dist_a: dict[str, int],
    dist_b: dict[str, int],
    label_a: str,
    label_b: str,
) -> None:
    """Render an overlaid bar chart comparing two distributions."""
    if not dist_a and not dist_b:
        st.info("No distribution data available for comparison.")
        return

    combined_keys = dist_a.keys() | dist_b.keys()
    all_keys = sorted(combined_keys, key=lambda x: int(x) if x.isdigit() else x)

    rows: list[dict[str, Any]] = []
    for key in all_keys:
        rows.append({"Depth": key, "Count": dist_a.get(key, 0), "Run": label_a})
        rows.append({"Depth": key, "Count": dist_b.get(key, 0), "Run": label_b})

    df = pl.DataFrame(rows)

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("Depth:N", title="Success Depth", sort=all_keys),
            y=alt.Y("Count:Q", title="Count"),
            color=alt.Color(
                "Run:N",
                scale=alt.Scale(
                    domain=[label_a, label_b],
                    range=[_COLOR_RUN_A, _COLOR_RUN_B],
                ),
            ),
            xOffset="Run:N",
            tooltip=[
                alt.Tooltip("Depth:N", title="Depth"),
                alt.Tooltip("Count:Q", title="Count", format=","),
                alt.Tooltip("Run:N", title="Run"),
            ],
        )
        .properties(
            title="Distribution Comparison",
            width="container",
            height=_CHART_HEIGHT,
        )
    )

    st.altair_chart(chart, use_container_width=True)


def _render_config_diff(
    config_a: dict[str, Any],
    config_b: dict[str, Any],
    label_a: str,
    label_b: str,
) -> None:
    """Render configuration differences between two runs."""
    all_keys = sorted(config_a.keys() | config_b.keys())

    diff_rows: list[dict[str, str]] = []
    for key in all_keys:
        val_a = config_a.get(key, "N/A")
        val_b = config_b.get(key, "N/A")
        changed = "Yes" if val_a != val_b else ""
        diff_rows.append(
            {
                "Parameter": key,
                label_a: str(val_a),
                label_b: str(val_b),
                "Changed": changed,
            }
        )

    if diff_rows:
        df = pl.DataFrame(diff_rows)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_comparison_view(
    run_a: dict[str, Any],
    run_b: dict[str, Any],
    label_a: str = "Run A",
    label_b: str = "Run B",
) -> None:
    """Side-by-side comparison of two simulation runs.

    Args:
        run_a: First run data dictionary (from LocalSimulationStore).
        run_b: Second run data dictionary (from LocalSimulationStore).
        label_a: Display label for the first run.
        label_b: Display label for the second run.
    """
    logger.info("Rendering comparison: %s vs %s", label_a, label_b)

    # -- KPI Metric Comparison --
    st.subheader("KPI Comparison")
    metrics_a = _extract_kpi_metrics(run_a)
    metrics_b = _extract_kpi_metrics(run_b)
    _render_metric_comparison(metrics_a, metrics_b, label_a, label_b)

    st.markdown("---")

    # -- Distribution Comparison --
    st.subheader("Distribution Comparison")
    dist_a: dict[str, int] = run_a.get("distribution", {})
    dist_b: dict[str, int] = run_b.get("distribution", {})
    _render_distribution_comparison(dist_a, dist_b, label_a, label_b)

    st.markdown("---")

    # -- Configuration Diff --
    st.subheader("Configuration Differences")
    config_a: dict[str, Any] = run_a.get("config", {})
    config_b: dict[str, Any] = run_b.get("config", {})
    _render_config_diff(config_a, config_b, label_a, label_b)
