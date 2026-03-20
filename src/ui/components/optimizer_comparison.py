"""Side-by-side comparison view for optimizer results.

Shows config diff, KPI deltas, and distribution overlay between the
original configuration and the AI-optimized configuration.

Pure helper functions (compute_config_diff, compute_kpi_deltas,
build_distribution_overlay_data) are fully testable without Streamlit.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import altair as alt
import polars as pl
import streamlit as st

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CHART_HEIGHT = 400
_COLOR_ORIGINAL = "#457B9D"
_COLOR_OPTIMIZED = "#FF6B35"

_LABEL_ORIGINAL = "Original"
_LABEL_OPTIMIZED = "Optimized"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigDiffRow:
    """One row in the config diff table."""

    parameter: str
    original_value: Any
    optimized_value: Any
    pct_change: float | None = None


@dataclass(frozen=True)
class KpiDelta:
    """Delta for a single KPI metric."""

    metric: str
    original: float
    optimized: float
    delta: float
    pct_change: float | None = None


# ---------------------------------------------------------------------------
# Pure helper functions (testable without Streamlit)
# ---------------------------------------------------------------------------


def compute_config_diff(
    original: dict[str, Any],
    optimized: dict[str, Any],
) -> list[ConfigDiffRow]:
    """Compute a list of parameter changes between two config dicts.

    Only returns rows for parameters that actually changed.
    For numeric scalar values, includes a percentage change.

    Args:
        original: The original configuration dictionary.
        optimized: The optimized configuration dictionary.

    Returns:
        List of ConfigDiffRow for changed parameters.
    """
    all_keys = sorted(original.keys() | optimized.keys())
    rows: list[ConfigDiffRow] = []

    for key in all_keys:
        val_orig = original.get(key)
        val_opt = optimized.get(key)

        if val_orig == val_opt:
            continue

        pct: float | None = None
        if (
            isinstance(val_orig, (int, float))
            and isinstance(val_opt, (int, float))
            and not isinstance(val_orig, bool)
            and not isinstance(val_opt, bool)
        ):
            if val_orig != 0:
                pct = ((val_opt - val_orig) / abs(val_orig)) * 100.0
            else:
                pct = None

        rows.append(
            ConfigDiffRow(
                parameter=key,
                original_value=val_orig,
                optimized_value=val_opt,
                pct_change=pct,
            )
        )

    return rows


def compute_kpi_deltas(
    original_kpis: dict[str, float],
    optimized_kpis: dict[str, float],
) -> list[KpiDelta]:
    """Compute deltas between original and optimized KPI values.

    Preserves the key order from original_kpis.

    Args:
        original_kpis: KPI metric name -> value for original run.
        optimized_kpis: KPI metric name -> value for optimized run.

    Returns:
        List of KpiDelta in the same order as original_kpis keys.
    """
    deltas: list[KpiDelta] = []

    for metric in original_kpis:
        orig = original_kpis[metric]
        opt = optimized_kpis.get(metric, 0.0)
        delta = opt - orig

        pct: float | None = None
        if orig != 0.0:
            pct = (delta / abs(orig)) * 100.0
        elif delta == 0.0:
            pct = 0.0
        else:
            pct = None

        deltas.append(
            KpiDelta(
                metric=metric,
                original=orig,
                optimized=opt,
                delta=delta,
                pct_change=pct,
            )
        )

    return deltas


def build_distribution_overlay_data(
    original_dist: dict[str, int],
    optimized_dist: dict[str, int],
    label_a: str = _LABEL_ORIGINAL,
    label_b: str = _LABEL_OPTIMIZED,
) -> list[dict[str, Any]]:
    """Build row data for an overlaid distribution bar chart.

    Args:
        original_dist: Depth -> count mapping for original run.
        optimized_dist: Depth -> count mapping for optimized run.
        label_a: Label for the original series.
        label_b: Label for the optimized series.

    Returns:
        List of dicts with keys Depth, Count, Run — sorted by depth.
    """
    combined_keys = original_dist.keys() | optimized_dist.keys()
    if not combined_keys:
        return []

    sorted_keys = sorted(combined_keys, key=lambda x: int(x) if x.isdigit() else x)

    rows: list[dict[str, Any]] = []
    for key in sorted_keys:
        rows.append({"Depth": key, "Count": original_dist.get(key, 0), "Run": label_a})
        rows.append({"Depth": key, "Count": optimized_dist.get(key, 0), "Run": label_b})

    return rows


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt(value: float) -> str:
    """Format a number — drop .00 for whole numbers."""
    if not math.isfinite(value):
        return f"{value}"
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _fmt_delta(value: float) -> str | None:
    """Format a delta value — None if zero."""
    if value == 0:
        return None
    if value == int(value):
        return f"{int(value):+,}"
    return f"{value:+,.2f}"


def _fmt_value(value: Any) -> str:
    """Format a config value for display."""
    if isinstance(value, list):
        return ", ".join(f"{v}" for v in value)
    if value is None:
        return "N/A"
    return str(value)


# ---------------------------------------------------------------------------
# Rendering (Streamlit)
# ---------------------------------------------------------------------------


def _render_config_diff_table(diff_rows: list[ConfigDiffRow]) -> None:
    """Render the config diff as a Polars DataFrame table."""
    if not diff_rows:
        st.info("No config parameters changed.")
        return

    table_rows: list[dict[str, str]] = []
    for row in diff_rows:
        pct_str = ""
        if row.pct_change is not None:
            pct_str = f"{row.pct_change:+.1f}%"

        table_rows.append(
            {
                "Parameter": row.parameter,
                "Original": _fmt_value(row.original_value),
                "Optimized": _fmt_value(row.optimized_value),
                "Change": pct_str,
            }
        )

    df = pl.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_kpi_comparison(deltas: list[KpiDelta]) -> None:
    """Render KPI comparison using st.metric with built-in delta display."""
    if not deltas:
        st.info("No KPI data available.")
        return

    col_orig, col_opt = st.columns(2)

    with col_orig:
        st.markdown("##### Original")
        for d in deltas:
            st.metric(label=d.metric, value=_fmt(d.original))

    with col_opt:
        st.markdown("##### Optimized")
        for d in deltas:
            st.metric(
                label=d.metric,
                value=_fmt(d.optimized),
                delta=_fmt_delta(d.delta),
            )


def _render_distribution_overlay(
    overlay_rows: list[dict[str, Any]],
    label_a: str = _LABEL_ORIGINAL,
    label_b: str = _LABEL_OPTIMIZED,
) -> None:
    """Render an overlaid bar chart comparing two distributions."""
    if not overlay_rows:
        st.info("No distribution data available for comparison.")
        return

    df = pl.DataFrame(overlay_rows)
    sorted_keys = list(dict.fromkeys(row["Depth"] for row in overlay_rows))

    chart = (
        alt.Chart(df)
        .mark_bar(opacity=0.7)
        .encode(
            x=alt.X("Depth:N", title="Success Depth", sort=sorted_keys),
            y=alt.Y("Count:Q", title="Count"),
            color=alt.Color(
                "Run:N",
                scale=alt.Scale(
                    domain=[label_a, label_b],
                    range=[_COLOR_ORIGINAL, _COLOR_OPTIMIZED],
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
            title="Distribution: Original vs Optimized",
            width="container",
            height=_CHART_HEIGHT,
        )
    )

    st.altair_chart(chart, use_container_width=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_optimizer_comparison(
    original_config: dict[str, Any],
    optimized_config: dict[str, Any],
    original_kpis: dict[str, float],
    optimized_kpis: dict[str, float],
    original_distribution: dict[str, int],
    optimized_distribution: dict[str, int],
) -> bool:
    """Render side-by-side optimizer comparison.

    Shows:
    1. Config diff table: parameter | original | optimized | change
    2. KPI comparison: metric | original | optimized | delta (with color)
    3. Distribution overlay chart
    4. "Apply Optimized Config" button

    Args:
        original_config: The config dict before optimization.
        optimized_config: The best config found by the optimizer.
        original_kpis: KPI metrics from the original simulation.
        optimized_kpis: KPI metrics from re-running with the optimized config.
        original_distribution: Success depth distribution from original run.
        optimized_distribution: Success depth distribution from optimized run.

    Returns:
        True if the user clicked "Apply Optimized Config".
    """
    st.markdown("#### Original vs Optimized Comparison")

    # -- KPI Comparison --
    st.markdown("##### KPI Comparison")
    kpi_deltas = compute_kpi_deltas(original_kpis, optimized_kpis)
    _render_kpi_comparison(kpi_deltas)

    st.markdown("---")

    # -- Config Diff --
    st.markdown("##### Configuration Changes")
    diff_rows = compute_config_diff(original_config, optimized_config)
    _render_config_diff_table(diff_rows)

    st.markdown("---")

    # -- Distribution Overlay --
    st.markdown("##### Distribution Overlay")
    overlay_data = build_distribution_overlay_data(
        original_distribution, optimized_distribution
    )
    _render_distribution_overlay(overlay_data)

    # -- Apply Button --
    return bool(
        st.button(
            "Apply Optimized Config",
            type="primary",
            use_container_width=True,
            key="opt_apply_comparison",
        )
    )
